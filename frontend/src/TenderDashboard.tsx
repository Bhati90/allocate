

// pages/TenderDashboard.tsx
import { useCallback, useEffect,useMemo,useRef, useState } from "react";
import axios from "axios";
import {Pencil,Pen,Check,X,
  Users, Briefcase, ChevronDown, ChevronUp,
  MapPin, Phone, Calendar, Layers, IndianRupee,
  TrendingUp, RefreshCw, Filter, Search, CheckCircle,
  Clock, AlertCircle, Building2, User, PlusCircle
} from "lucide-react";
import { useNavigate } from 'react-router-dom';

import { AddToClusterModal } from "./Tender";
import { API_BASE_URL } from "./types/config";
// const API_BASE = "http://localhost:8002/tender";
// const API_BASE_URL = "http://localhost:8002/tender";

import toast from "react-hot-toast";
import Dialpad from "./call";
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
  // In your TypeScript interfaces, update clusters:
clusters: {
  id: number;
  name: string;
  mukkadam_type: 'permanent' | 'updown';
  updown_mode?: 'range' | 'specific';
  updown_from_date?: string;
  updown_to_date?: string;
  updown_specific_dates?: string[];
}[];

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
  summary: {
    total_mukkadams:     number;
    total_farmers:       number;
    total_tender_jobs:   number;
    total_activities:    number;
    total_plots:         number;
    total_acres:         number;
    total_booking_value: number;
    total_advance_paid:  number;
    total_balance:       number;
    paid_jobs:           number;
    partial_paid_jobs:   number;
  };
  mukkadams: Mukkadam[];
  farmers:   Farmer[];
}
interface ClusterOption { id: number; name: string;mukkadam_type?: 'permanent' | 'updown';
  updown_mode?: 'range' | 'specific';
  updown_from_date?: string | null;
  updown_to_date?: string | null;
  updown_specific_dates?: string[] | null;

  transport_price?: number | null;
  weekly_payment_day?: number | null;
  advance_amount?: number | null;
  weekly_amount?: number | null;

  // frontend-only
  isEdit?: boolean; }

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

  // Close on outside click
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

  // ❌ REMOVED: scroll listener was firing immediately because
  // autoFocus on the search input causes browser to scroll,
  // which triggered onClose() right away → dropdown closed instantly
  // and the page jumped to top.

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
function MukkadamCard({ m, clusters, onSuccess ,onCallClick,isAdmin = false}: {
  m: Mukkadam;
  clusters: ClusterOption[];
  onSuccess: () => void;
  onCallClick: (number: string) => void;
  isAdmin?: boolean;
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
                <p className="text-xs text-gray-500 flex items-center gap-2">
  <span className="inline-flex items-center gap-1">
    <Phone size={11} /> {m.mobile}
  </span>
  <button
    type="button"
    onClick={(e) => {
  e.stopPropagation();
  console.log('Call clicked for', m.mobile);
  onCallClick(m.mobile);
}}

    className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-green-50 text-green-700 border border-green-200 hover:bg-green-100"
  >
    Call
  </button>
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

              {/* Cluster pills with edit button */}
              {m.clusters.length === 0 ? (
                <span className="px-2 py-0.5 bg-red-50 text-red-500 rounded text-xs">
                  No Cluster
                </span>
              ) : (
                m.clusters.map((c: ClusterOption) => (
                  
                  <span
                    key={c.id}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '2px 8px',
                      borderRadius: '6px',
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      background:
                        c.mukkadam_type === 'updown' ? '#fff7ed' : '#f0fdfa',
                      color:
                        c.mukkadam_type === 'updown' ? '#c2410c' : '#0f766e',
                      border: `1px solid ${
                        c.mukkadam_type === 'updown' ? '#fed7aa' : '#99f6e4'
                      }`,
                    }}
                  >
                    {c.mukkadam_type === 'updown' ? '📅' : '🏠'} {c.name}
                    {c.mukkadam_type === 'updown' && (
                      <span style={{ opacity: 0.7, fontWeight: 400 }}>
                        {c.updown_mode === 'range'
                          ? ` · ${c.updown_from_date} → ${c.updown_to_date}`
                          : ` · ${(c.updown_specific_dates || []).length} days`}
                      </span>
                    )}

                    {/* ✎ Edit assignment for this cluster */}
                     <MukkadamAddToCluster
                      mukkadam={m}
                      clusters={clusters}
                      onSuccess={onSuccess}
                      mode="edit"
                      clusterToEdit={c}
                    />

                    {isAdmin && (
  <button
    onClick={async (e) => {
      const token = localStorage.getItem('auth_token')
      e.stopPropagation();
      if (!confirm(`Remove ${m.name} from "${c.name}"?`)) return;
      await fetch(`${API_BASE_URL}/api/clusters/${c.id}/remove_mukkadam/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json','Authorization': `Token ${token}`, },
        
        body: JSON.stringify({ mukkadam_id: m.id }),
      });
      onSuccess();
    }}
    title="Remove from cluster"
    style={{
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      padding: '0 2px',
      lineHeight: 1,
      color: '#ef4444',
      opacity: 0.7,
      fontSize: '0.75rem',
    }}
    onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
    onMouseLeave={e => (e.currentTarget.style.opacity = '0.7')}
  >
    ✕
  </button>
)}
                  </span>
                  
                ))
              )}

              {/* Add to Cluster — separate trigger */}
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                }}
              >
                 <MukkadamAddToCluster
                mukkadam={m}
                clusters={clusters}
                onSuccess={onSuccess}
                mode="add"
              />
              </div>
            </div>
          </div>

          <div className="text-right ml-4">
            {expanded ? (
              <ChevronUp size={16} className="ml-auto text-gray-400 mt-1" />
            ) : (
              <ChevronDown size={16} className="ml-auto text-gray-400 mt-1" />
            )}
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
import { GlobalInsightsPanel } from "./Global";

// ─── Plot Cluster Control ─────────────────────────────────
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

  const openPicker = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + window.scrollY + 6,
        right: window.innerWidth - rect.right,
      });
    }
    setShowPicker(v => !v);
  };

  // Close on outside click only — NO scroll listener (scroll listener
  // was firing immediately because autoFocus caused browser scroll → closed dropdown)
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

  // ❌ REMOVED scroll listener — was causing scroll-to-top

  const plotClusterIds = new Set(
    clusterGroups
      .filter(g => g.cluster_id !== null && g.plots.some(p => p.plot_id === plot.plot_id))
      .map(g => g.cluster_id!)
  );
  const plotClusters = clusterGroups
    .filter(g => g.cluster_id !== null && g.plots.some(p => p.plot_id === plot.plot_id))
    .map(g => ({ id: g.cluster_id!, name: g.cluster_name }));

  const handleAddPlot = async (cluster: ClusterOption) => {

    const token = localStorage.getItem('auth_token')
    if (saving) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/cluster/${cluster.id}/add_farmer/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json','Authorization':`Token ${token}` },
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
        type="button"
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

      {/* Portal dropdown */}
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
                  type="button"
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
        document.body
      )}
    </div>
  );
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
  const btnRef = useRef<HTMLButtonElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);  // ← manual focus, no autoFocus
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });

  // Close on outside click only — NO scroll listener
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropRef.current && !dropRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setShowPicker(false);
        setSearch('');
      }
    };
    if (showPicker) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showPicker]);

  // Focus search AFTER portal mounts, with preventScroll
  useEffect(() => {
    if (showPicker) {
      setTimeout(() => {
        searchRef.current?.focus({ preventScroll: true });
      }, 0);
    }
  }, [showPicker]);

  const openPicker = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + window.scrollY + 6,
        left: rect.left,
      });
    }
    setShowPicker(v => !v);
  };

  const filtered = clusters.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleAddToCluster = async (cluster: ClusterOption) => {
    const token = localStorage.getItem('auth_token')
    if (saving) return;
    setSaving(true);
    try {
      const allPlotIds = farmer.plots_by_cluster.flatMap(g => g.plots.map(p => p.plot_id));
      const res = await fetch(`${API_BASE_URL}/api/cluster/${cluster.id}/add_farmer/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' ,'Authorization':`Token ${token}`},
        body: JSON.stringify({ farmer_id: farmer.farmer_id, plot_ids: allPlotIds }),
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

  const fullyInCluster = (clusterId: number) => {
    const group = farmer.plots_by_cluster.find(g => g.cluster_id === clusterId);
    const allPlotIds = new Set(farmer.plots_by_cluster.flatMap(g => g.plots.map(p => p.plot_id)));
    const inClusterIds = new Set(group?.plots.map(p => p.plot_id) || []);
    return allPlotIds.size > 0 && [...allPlotIds].every(id => inClusterIds.has(id));
  };

  return (
    <>
      <button
        type="button"
        ref={btnRef}
        onClick={openPicker}
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

      {/* Portal dropdown — escapes overflow:hidden parents, no scroll jump */}
      {showPicker && ReactDOM.createPortal(
        <div
          ref={dropRef}
          onClick={e => e.stopPropagation()}
          style={{
            position: 'absolute',
            top: dropdownPos.top,
            left: dropdownPos.left,
            zIndex: 99999,
            background: '#fff',
            borderRadius: '12px',
            border: '1px solid #e5e7eb',
            boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
            width: '220px',
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: '10px 12px 6px', borderBottom: '1px solid #f3f4f6' }}>
            <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Add all plots to cluster
            </p>
          </div>

          <div style={{ padding: '8px 10px', borderBottom: '1px solid #f3f4f6' }}>
            <input
              ref={searchRef}
              // autoFocus REMOVED — was triggering scroll → closing dropdown immediately
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

          <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {filtered.length === 0 ? (
              <p style={{ padding: '12px', textAlign: 'center', fontSize: '0.8rem', color: '#9ca3af' }}>
                No clusters found
              </p>
            ) : filtered.map(c => {
              const allIn = fullyInCluster(c.id);
              return (
                <button
                  type="button"
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
        </div>,
        document.body
      )}
    </>
  );
}
// ─── Farmer Card ─────────────────────────────────────────
interface FarmerCardProps {
  farmer: Farmer;
  clusters: ClusterOption[];
  isAdmin?: boolean;
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
function FarmerCard({ farmer, clusters, onSuccess,isAdmin = false }: FarmerCardProps) {
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
  <span key={c.id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-teal-50 text-teal-700 rounded text-xs">
    {c.name}

    {isAdmin && (
      <button
        onClick={async (e) => {
          e.stopPropagation();
          if (!confirm(`Remove ${farmer.farmer_name} from "${c.name}"?`)) return;
          const token = localStorage.getItem('auth_token');
          await fetch(`${API_BASE_URL}/api/clusters/${c.id}/remove_farmer/`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Token ${token}`,
            },
            body: JSON.stringify({ farmer_id: farmer.farmer_id }),
          });
          onSuccess();
        }}
        title="Remove from cluster"
        className="ml-0.5 text-red-400 hover:text-red-600 leading-none"
      >
        ✕
      </button>
    )}
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



// ─── Main Page ───────────────────────────────────────────
export default function TenderDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);


  const [farmerSubTab, setFarmerSubTab] = useState<'all' | 'full' | 'partial' | 'none' | 'new'>('all');
   const navigate = useNavigate();

   const [isAdmin, setIsAdmin] = useState(false);


   

useEffect(() => {
  const token = localStorage.getItem('auth_token'); // ← use whatever key you store it under

  fetch(`${API_BASE_URL}/auth/me/`, {
    headers: {
      'Authorization': `Token ${token}`,   // or `Bearer ${token}` if using JWT
      'Content-Type': 'application/json',
    },
  })
    .then(r => r.ok ? r.json() : null)
    .then(d => { if (d?.is_admin) setIsAdmin(true); })
    .catch(() => {});
}, []);
  // Change the tab type
// change tab type
const [tab, setTab] = useState<'mukkadams' | 'farmers' | 'jobs' | 'global'>('mukkadams');

  const [search, setSearch] = useState('');
  const [clusterFilter, setClusterFilter] = useState('');
  const [clusters, setClusters] = useState<ClusterOption[]>([]);
// Add alongside clusterFilter state
const [noCluster, setNoCluster] = useState(false);


const [dialpadOpen, setDialpadOpen] = useState(false);
const [dialpadNumber, setDialpadNumber] = useState('');
const [actTotalCount, setActTotalCount] = useState<number>(0);



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
        axios.get(`${API_BASE_URL}/api/tender-dashboard/`, { params }),
        axios.get(`${API_BASE_URL}/api/clusters/`),
      ]);
      setData(dashRes.data);
      setClusters(clusterRes.data?.results || clusterRes.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // ── ADD THIS ─────────────────────────────────────────────────────
  // Silent refresh — no spinner, no scroll-to-top.
  // Used by MukkadamCard/FarmerCard onSuccess after add-to-cluster.
  const fetchDataSilent = async () => {
    const scrollY = window.scrollY;          // save position BEFORE fetch
    try {
      const params: Record<string, string> = {};
      if (clusterFilter) params.cluster_id = clusterFilter;

      const [dashRes, clusterRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/tender-dashboard/`, { params }),
        axios.get(`${API_BASE_URL}/api/clusters/`),
      ]);
      setData(dashRes.data);
      setClusters(clusterRes.data?.results || clusterRes.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      // Restore scroll after React re-renders (two frames to be safe)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          window.scrollTo({ top: scrollY, behavior: 'instant' });
        });
      });
    }
  };
  // ─────────────────────────────────────────────────────────────────



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
// Replace job states with activity states
const [activities, setActivities] = useState<any[]>([]);        // current view (filtered)
const [allActivities, setAllActivities] = useState<any[]>([]);  // always the full unfiltered set
const [actLoading, setActLoading]       = useState(false);
const [actCluster, setActCluster]       = useState('');
const [actSearch, setActSearch]         = useState('');
const [actDateFrom, setActDateFrom]     = useState('');
const [actDateTo, setActDateTo]         = useState('');
const [actSubTab, setActSubTab]         = useState<'all' | 'upcoming' | 'last10' | 'not_allocated' | 'in_progress' |'split'| 'completed'>('all');
const [expandedActJob, setExpandedActJob] = useState<string | null>(null);
// Add this ref alongside your states
const allActivitiesRef = useRef<any[]>([]);

// Update fetchActivities — remove allActivities from deps
const fetchActivities = useCallback(async () => {
  setActLoading(true);
  try {
    const params: Record<string, string> = {};
    if (actCluster)  params.cluster_id = actCluster;
    if (actDateFrom) params.date_from  = actDateFrom;
    if (actDateTo)   params.date_to    = actDateTo;
    if (actSearch)   params.search     = actSearch;
    if (actSubTab === 'upcoming')      params.upcoming = '1';
    if (actSubTab === 'last10')        params.last10   = '1';
    if (actSubTab === 'not_allocated') params.status   = 'pending';
    if (actSubTab === 'in_progress')   params.status   = 'in_progress';
    if (actSubTab === 'completed')     params.status   = 'completed';

    if (actSubTab === 'split') {
      // No API call needed — filter from ref
      setActivities(allActivitiesRef.current.filter((a: any) => a.is_split === true));
      setActLoading(false);
      return;
    }

    const res = await axios.get(`${API_BASE_URL}/api/activity-dashboard/`, { params });
    const fetched = (res.data?.activities || []).filter((a: any) => a.total_area > 0);

    setActivities(fetched);

    if (actSubTab === 'all' && !actSearch && !actDateFrom && !actDateTo) {
      allActivitiesRef.current = fetched;   // update ref (no re-render trigger)
      setAllActivities(fetched);     
      
      if (actSubTab === 'all' && !actSearch && !actDateFrom && !actDateTo) {
  allActivitiesRef.current = fetched;
  setAllActivities(fetched);
  
  // DEBUG
  console.log('=== ACTIVITY DEBUG ===');
  console.log('Total fetched:', fetched.length);
  console.log('Sample activity:', fetched[0]);
  console.log('Allocation count > 0:', fetched.filter((a: any) => a.allocation_count > 0).length);
  console.log('Has allocations array:', fetched.filter((a: any) => a.allocations?.length > 0).length);
  console.log('All completed:', fetched.filter((a: any) => 
    a.allocation_count > 0 && a.allocations?.every((alloc: any) => alloc.work_status === 'completed')
  ).length);
  console.log('Work statuses sample:', fetched
    .filter((a: any) => a.allocation_count > 0)
    .slice(0, 3)
    .map((a: any) => ({ 
      id: a.activity_id, 
      allocation_count: a.allocation_count,
      allocations_length: a.allocations?.length,
      statuses: a.allocations?.map((al: any) => al.work_status)
    }))
  );
}// update state for counts display
    }
  } catch (e) {
    console.error(e);
  } finally {
    setActLoading(false);
  }
}, [actCluster, actDateFrom, actDateTo, actSearch, actSubTab]); // ← allActivities REMOVED
useEffect(() => {
  if (tab !== 'jobs') return;
  fetchActivities();
}, [tab, fetchActivities]);

// Remove the separate debounced search useEffect — useCallback handles it
// In fetchActivities, the 'all' fetch already gets everything
// The issue is actCounts.completed filters allActivities but 
// allActivities has allocation_status = 'fully_allocated', NOT 'completed'

// Fix actCounts.completed — the activity has work_status=completed on allocation
// but allocation_status='fully_allocated' on the activity itself

const actCounts = {
  all:           allActivities.length,
  upcoming:      allActivities.filter((a: any) => 
    a.days_until !== null && a.days_until >= 0 && a.days_until <= 10).length,
  last10:        allActivities.filter((a: any) => 
    a.days_until !== null && a.days_until >= -10 && a.days_until <= 0).length,
  not_allocated: allActivities.filter((a: any) => 
    a.allocation_status === 'pending').length,
  in_progress:   allActivities.filter((a: any) =>
    a.allocation_count > 0 &&
    !a.allocations?.every((alloc: any) => alloc.work_status === 'completed')
  ).length,
  completed: allActivities.filter((a: any) =>
  a.allocations?.some((alloc: any) => alloc.work_status === 'completed')
).length,
  split: allActivities.filter((a: any) => a.is_split === true).length,
};
// Filter by sub-tab on frontend
const today     = new Date();
const in10Days  = new Date(); in10Days.setDate(today.getDate() + 10);


const sevenDaysAgo = new Date(today);
sevenDaysAgo.setDate(today.getDate() - 7);

const classifyFarmer = (f: any) => {
  const plotsByCluster: any[] = f.plots_by_cluster || [];
  
  // Count plots with NO cluster
  const noneGroup = plotsByCluster.find((g: any) => g.cluster_id === null);
  const plotsWithoutCluster = noneGroup ? noneGroup.plots.length : 0;
  
  // Count plots WITH a cluster
  const plotsWithCluster = plotsByCluster
    .filter((g: any) => g.cluster_id !== null)
    .reduce((sum: number, g: any) => sum + g.plots.length, 0);

  const totalPlots = f.total_plots || 0;

  if (plotsWithCluster === 0) return 'none';
  if (plotsWithoutCluster === 0 || plotsWithCluster >= totalPlots) return 'full';
  return 'partial';
};

// New farmer check
const isNewFarmer = (f: any) => {
  if (!f.newest_job_date) return false;
  return new Date(f.newest_job_date) >= sevenDaysAgo;
};

// Updated counts
const farmerCounts = {
  all:     filteredFarmers.length,
  new:     filteredFarmers.filter(isNewFarmer).length,
  full:    filteredFarmers.filter((f: any) => classifyFarmer(f) === 'full').length,
  partial: filteredFarmers.filter((f: any) => classifyFarmer(f) === 'partial').length,
  none:    filteredFarmers.filter((f: any) => classifyFarmer(f) === 'none').length,
};

// Updated subTabFilteredFarmers
const subTabFilteredFarmers = filteredFarmers.filter((f: any) => {
  if (farmerSubTab === 'all')     return true;
  if (farmerSubTab === 'new')     return isNewFarmer(f);
  return classifyFarmer(f) === farmerSubTab;
});

const [expandedJobKey, setExpandedJobKey] = useState<string | null>(null);
// Compute stats from currently visible farmers when sub-tab is active
const displaySummary = useMemo(() => {
  if (!data) return null;
  if (farmerSubTab === 'all' || tab !== 'farmers') return data.summary;

  const visibleFarmers = subTabFilteredFarmers;

  let bookingValue = 0;
  let advancePaid  = 0;
  const jobIdsSeen  = new Set<string>();
  const plotIdsSeen = new Set<number>();

  visibleFarmers.forEach((f: any) => {
    (f.plots_by_cluster || []).forEach((group: any) => {
      (group.plots || []).forEach((p: any) => {
        // deduplicate plots
        if (!plotIdsSeen.has(p.plot_id)) {
          plotIdsSeen.add(p.plot_id);
        }

        (p.jobs || []).forEach((j: any) => {
          if (jobIdsSeen.has(j.job_id)) return;
          jobIdsSeen.add(j.job_id);
          if (j.booking) {
            bookingValue += j.booking.total_amount || 0;
            advancePaid  += j.booking.advance_paid || 0;
          }
        });
      });
    });
  });

  // acres = sum of area_acres for unique plots only
  const totalAcres = visibleFarmers.reduce((sum: number, f: any) => {
    const seenInFarmer = new Set<number>();
    (f.plots_by_cluster || []).forEach((group: any) => {
      (group.plots || []).forEach((p: any) => {
        if (!seenInFarmer.has(p.plot_id)) {
          seenInFarmer.add(p.plot_id);
          sum += p.area_acres || 0;
        }
      });
    });
    return sum;
  }, 0);

  return {
  ...data.summary,
  total_farmers:       visibleFarmers.length,
  total_tender_jobs:   jobIdsSeen.size,
  total_plots:         plotIdsSeen.size,
  total_acres:         totalAcres,
  total_booking_value: bookingValue,
  total_advance_paid:  advancePaid,
  total_balance:       bookingValue - advancePaid,
  // ── COMPUTE activities from visible farmers ──
  total_activities:    (() => {
    const activityKeys = new Set<string>();
    visibleFarmers.forEach((f: any) => {
      (f.plots_by_cluster || []).forEach((group: any) => {
        (group.plots || []).forEach((p: any) => {
          (p.jobs || []).forEach((j: any) => {
            (j.activities || []).forEach((a: any) => {
              if (a.total_area > 0) {
                // key = job + plot + activity name (same logic as backend)
                activityKeys.add(`${j.job_id}-${p.plot_id}-${a.name}`);
              }
            });
          });
        });
      });
    });
    return activityKeys.size;
  })(),
};
}, [data, farmerSubTab, subTabFilteredFarmers, tab]);






  
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
        onClick={() => navigate('/')}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-200 text-sm text-gray-700 bg-white hover:bg-gray-50"
      >
        ← Back
      </button>
 
        </div>

        {displaySummary && (
  <div style={{ marginBottom: '16px' }}>
    {/* Row 1 — existing 3 stats */}
    <div className="grid grid-cols-3 gap-3 mb-3">
      {[
        { label: 'Mukkadams',   value: displaySummary?.total_mukkadams,   color: 'text-teal-600',   bg: 'bg-teal-50' },
        { label: 'Farmers',     value: displaySummary?.total_farmers,     color: 'text-blue-600',   bg: 'bg-blue-50' },
        { label: 'Tender Jobs', value: displaySummary?.total_tender_jobs, color: 'text-purple-600', bg: 'bg-purple-50' },
      ].map(s => (
        <div key={s.label} className={`${s.bg} rounded-xl p-3 text-center`}>
          <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          <p className="text-xs text-gray-500">{s.label}</p>
        </div>
      ))}
    </div>

    {/* Row 2 — new stats */}
    <div className="grid grid-cols-3 gap-3 mb-3">
      {[
        { label: 'Activities',  value: displaySummary?.total_activities,  color: 'text-orange-600', bg: 'bg-orange-50' },
        { label: 'Plots',       value: displaySummary?.total_plots,       color: 'text-pink-600',   bg: 'bg-pink-50' },
        { label: 'Total Acres', value: displaySummary?.total_acres ? `${Number(displaySummary.total_acres).toFixed(1)} ac` : '—', color: 'text-green-600', bg: 'bg-green-50' },
      ].map(s => (
        <div key={s.label} className={`${s.bg} rounded-xl p-3 text-center`}>
          <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
          <p className="text-xs text-gray-500">{s.label}</p>
        </div>
      ))}
    </div>

    {/* Row 3 — financial stats */}
    <div className="grid grid-cols-3 gap-3">
      <div className="bg-indigo-50 rounded-xl p-3 text-center">
        <p className="text-lg font-bold text-indigo-600">
          ₹{Number(displaySummary?.total_booking_value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
        </p>
        <p className="text-xs text-gray-500">Booking Value</p>
      </div>
      <div className="bg-emerald-50 rounded-xl p-3 text-center">
        <p className="text-lg font-bold text-emerald-600">
          ₹{Number(displaySummary?.total_advance_paid || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
        </p>
        <p className="text-xs text-gray-500">Advance Collected</p>
        <div style={{ display: 'flex', justifyContent: 'center', gap: '6px', marginTop: '3px' }}>
          <span style={{ fontSize: '0.58rem', background: '#dcfce7', color: '#15803d', padding: '1px 6px', borderRadius: '999px', fontWeight: 600 }}>
            ✅ {displaySummary?.paid_jobs} Paid
          </span>
          <span style={{ fontSize: '0.58rem', background: '#fef9c3', color: '#b45309', padding: '1px 6px', borderRadius: '999px', fontWeight: 600 }}>
            ⚡ {displaySummary?.partial_paid_jobs} Partial
          </span>
        </div>
      </div>
      <div className="bg-red-50 rounded-xl p-3 text-center">
        <p className="text-lg font-bold text-red-600">
          ₹{Number(displaySummary?.total_balance || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
        </p>
        <p className="text-xs text-gray-500">Balance Due</p>
      </div>
    </div>
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
  onClick={() => { setTab('farmers'); setNoCluster(false); setClusterFilter(''); setFarmerSubTab('all'); }}
  className={`px-5 py-2 text-sm font-medium transition ${tab === 'farmers' ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
>
  <User size={15} className="inline mr-1" />
  Farmers ({data?.farmers?.length || 0})
</button>

<button
  onClick={() => { setTab('jobs'); setNoCluster(false); setClusterFilter(''); }}
  className={`px-5 py-2 text-sm font-medium transition ${tab === 'jobs' ? 'bg-green-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
>

💼 Jobs ({
  tab === 'jobs' && (actSubTab !== 'all' || actSearch || actCluster || actDateFrom || actDateTo)
    ? activities.length
    : data?.summary?.total_activities || 0
})

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
            <MukkadamCard
              key={m.id}
              m={m}
              clusters={clusters}
              isAdmin={isAdmin}
              onSuccess={fetchDataSilent}
              onCallClick={(num: string) => {
                setDialpadNumber(num || '');
                setDialpadOpen(true);
              }}
            />
          ))
      }
      <Dialpad
        isOpen={dialpadOpen}
        number={dialpadNumber}
        onClose={() => setDialpadOpen(false)}
        onNumberChange={setDialpadNumber}
      />
    </div>

  ) : tab === 'farmers' ? (
    <div className="space-y-3">
      {/* ── Farmer Sub-tabs ── */}
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '4px' }}>
        {([
          { key: 'all',     label: '📋 All',        color: '#6b7280', bg: '#f3f4f6', activeBg: '#374151', activeText: '#fff' },
          { key: 'new',     label: '🆕 New',         color: '#0369a1', bg: '#e0f2fe', activeBg: '#0369a1', activeText: '#fff' },
          { key: 'full',    label: '✅ Full',         color: '#15803d', bg: '#dcfce7', activeBg: '#15803d', activeText: '#fff' },
          { key: 'partial', label: '⚡ Partial',     color: '#b45309', bg: '#fef9c3', activeBg: '#b45309', activeText: '#fff' },
          { key: 'none',    label: '⚠️ No Cluster',  color: '#dc2626', bg: '#fef2f2', activeBg: '#dc2626', activeText: '#fff' },
        ] as const).map(t => {
          const isActive = farmerSubTab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setFarmerSubTab(t.key)}
              style={{
                padding: '5px 12px', borderRadius: '999px',
                border: `1.5px solid ${isActive ? t.activeBg : t.bg}`,
                background: isActive ? t.activeBg : t.bg,
                color: isActive ? t.activeText : t.color,
                fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
                transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: '5px',
              }}
            >
              {t.label}
              <span style={{
                background: isActive ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.08)',
                borderRadius: '999px', padding: '0px 6px', fontSize: '0.65rem', fontWeight: 700,
              }}>
                {farmerCounts[t.key]}
              </span>
            </button>
          );
        })}
      </div>

      {/* ── Farmer List ── */}
      {subTabFilteredFarmers.length === 0
        ? <div className="text-center py-16 text-gray-400">No farmers found</div>
        : subTabFilteredFarmers.map((f: any) => (
            <FarmerCard key={f.farmer_id} farmer={f} clusters={clusters} isAdmin={isAdmin} onSuccess={fetchDataSilent} />
          ))
      }
    </div>

 ) : tab === 'jobs' ? (
  <div>
    {/* Sub-tabs */}
    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '12px' }}>
      {([
        { key: 'all',           label: '📋 All',           color: '#6b7280', activeBg: '#374151' },
        { key: 'upcoming',      label: '📅 Next 10 Days',   color: '#0369a1', activeBg: '#0369a1' },
        { key: 'last10', label: '🕐 Last 10 Days', color: '#6b21a8', activeBg: '#6b21a8'},
          { key: 'split', label: '🔀 Split', color: '#7c3aed', activeBg: '#7c3aed' },
        { key: 'not_allocated', label: '⚠️ Not Allocated',  color: '#dc2626', activeBg: '#dc2626' },
        { key: 'in_progress',   label: '⚡ In Progress',    color: '#b45309', activeBg: '#b45309' },
        { key: 'completed',     label: '✅ Completed',      color: '#15803d', activeBg: '#15803d' },
      ] as const).map(t => {
        const isActive = actSubTab === t.key;
        return (
          <button key={t.key} onClick={() => setActSubTab(t.key)} style={{
            padding: '5px 12px', borderRadius: '999px', fontSize: '0.72rem', fontWeight: 600,
            cursor: 'pointer', border: 'none',
            background: isActive ? t.activeBg : '#f3f4f6',
            color: isActive ? '#fff' : t.color,
          }}>
            {t.label}
            <span style={{ marginLeft: '5px', background: 'rgba(0,0,0,0.1)', borderRadius: '999px', padding: '0 6px', fontSize: '0.65rem' }}>
              {actCounts[t.key]}
            </span>
          </button>
        );
      })}
    </div>

    {/* Filters */}
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
      <input
        placeholder="🔍 Search farmer / activity / plot"
        value={actSearch}
        onChange={e => setActSearch(e.target.value)}
        style={{ flex: 1, minWidth: '160px', padding: '7px 12px', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '0.82rem' }}
      />
      
<select value={actCluster} onChange={e => { 
  setActCluster(e.target.value); 
  setActSubTab('all');  // ← ADD THIS
}}
  style={{ padding: '7px 12px', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '0.82rem' }}>
  <option value="">All Clusters</option>
  {clusters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
</select>
      <input type="date" value={actDateFrom} onChange={e => setActDateFrom(e.target.value)}
        style={{ padding: '7px 10px', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '0.82rem' }} />
      <span style={{ alignSelf: 'center', color: '#9ca3af' }}>–</span>
      <input type="date" value={actDateTo} onChange={e => setActDateTo(e.target.value)}
        style={{ padding: '7px 10px', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '0.82rem' }} />
      {(actDateFrom || actDateTo) && (
        <button onClick={() => { setActDateFrom(''); setActDateTo(''); }}
          style={{ padding: '4px 8px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#fff', cursor: 'pointer', fontSize: '0.72rem', color: '#6b7280' }}>✕</button>
      )}
    </div>

    {/* Activity Cards */}
    {actLoading ? (
      <div className="flex justify-center py-16"><RefreshCw size={28} className="animate-spin text-green-400" /></div>
    ) : activities.length === 0 ? (
      <div className="text-center py-16 text-gray-400">No activities found</div>
    ) : (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {activities.map((a: any) => {
          const isExpanded   = expandedActJob === String(a.activity_id);
          const isPending    = a.allocation_status === 'pending';
          const isCompleted = a.allocations?.some((alloc: any) => alloc.work_status === 'completed');
  console.log(isCompleted)
          const isUpcoming   = a.days_until !== null && a.days_until >= 0 && a.days_until <= 10;

          return (
            <div key={a.activity_id} style={{
              border: `1.5px solid ${isPending ? '#fecaca' : isCompleted ? '#bbf7d0' : '#e5e7eb'}`,
              borderRadius: '12px', background: '#fff', overflow: 'hidden',
            }}>

              {/* ── COLLAPSED HEADER ── */}
              <div
                onClick={() => setExpandedActJob(isExpanded ? null : String(a.activity_id))}
                style={{ padding: '10px 14px', cursor: 'pointer' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Row 1 — activity name + status badges */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#111827' }}>{a.activity_name}</span>
                      {/* Allocation status */}
                      <span style={{
                        fontSize: '0.6rem', padding: '1px 7px', borderRadius: '999px', fontWeight: 600,
                        background: isPending          ? '#fef2f2'
                                  : isCompleted        ? '#f0fdf4'
                                  : a.allocation_status === 'fully_allocated' ? '#dcfce7'
                                  : '#fef9c3',
                        color: isPending          ? '#dc2626'
                             : isCompleted        ? '#16a34a'
                             : a.allocation_status === 'fully_allocated' ? '#15803d'
                             : '#b45309',
                      }}>{a.allocation_status}</span>
                      {isUpcoming && (
                        <span style={{ fontSize: '0.6rem', padding: '1px 7px', borderRadius: '999px', fontWeight: 700, background: '#fef9c3', color: '#b45309' }}>
                          📅 In {a.days_until}d
                        </span>
                      )}
                      {a.days_until !== null && a.days_until < 0 && !isCompleted && (
                        <span style={{ fontSize: '0.6rem', padding: '1px 7px', borderRadius: '999px', fontWeight: 700, background: '#fef2f2', color: '#dc2626' }}>
                          ⚠ Overdue {Math.abs(a.days_until)}d
                        </span>
                      )}
                      {/* After existing badges in Row 1 */}
{a.is_split && (
  <span style={{ 
    fontSize: '0.6rem', padding: '1px 7px', borderRadius: '999px', 
    fontWeight: 700, background: '#f3e8ff', color: '#7c3aed' 
  }}>
    🔀 Split {a.splits?.length}x
  </span>
)}
                    </div>

                    {/* Row 2 — farmer + plot + cluster */}
                    <div style={{ fontSize: '0.7rem', color: '#374151', marginTop: '3px', fontWeight: 600 }}>
                      👤 {a.farmer_name}
                      <span style={{ fontWeight: 400, color: '#6b7280' }}> · 📞 {a.farmer_phone || '—'}</span>
                    </div>
                    <div style={{ fontSize: '0.68rem', color: '#6b7280', marginTop: '2px' }}>
                      📍 {a.plot_name} {a.plot_code ? `[${a.plot_code}]` : ''} · {a.plot_area} ac
                      {a.clusters?.length > 0 && ` · 🏘 ${a.clusters.map((c: any) => c.name).join(', ')}`}
                    </div>

                    {/* Row 3 — dates + area + rate */}
                    <div style={{ display: 'flex', gap: '10px', marginTop: '4px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.65rem', color: '#6b7280' }}>🗓 Scheduled: {a.scheduled_date || '—'}</span>
                      <span style={{ fontSize: '0.65rem', color: '#0f766e' }}>🌾 {a.allocated_area}/{a.total_area} ac</span>
                      <span style={{ fontSize: '0.65rem', color: '#6b7280' }}>₹{a.rate_per_acre}/ac</span>
                      <span style={{ fontSize: '0.65rem', color: '#374151', fontWeight: 600 }}>
                        Farmer: ₹{Number(a.total_price).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                      </span>
                      {a.total_mukkadam_est > 0 && (
                        <span style={{ fontSize: '0.65rem', color: '#7c3aed', fontWeight: 600 }}>
                          Mukkadam: ₹{Number(a.total_mukkadam_est).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Right — allocation count + expand */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', marginLeft: '8px' }}>
                    <span style={{
                      fontSize: '0.65rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 600,
                      background: a.allocation_count > 0 ? '#eff6ff' : '#f3f4f6',
                      color: a.allocation_count > 0 ? '#1d4ed8' : '#9ca3af',
                    }}>
                      👷 {a.allocation_count} alloc{a.allocation_count !== 1 ? 's' : ''}
                    </span>
                    <span style={{ fontSize: '0.62rem', color: '#9ca3af' }}>{isExpanded ? '▲' : '▼'}</span>
                  </div>
                </div>
              </div>

              {/* ── EXPANDED — Allocations ── */}
              {isExpanded && (
                <div style={{ borderTop: '1px solid #e5e7eb', background: '#fafafa', padding: '10px 14px' }}>
                  {/* Job ref */}
                  <div style={{ fontSize: '0.65rem', color: '#9ca3af', marginBottom: '8px' }}>
                    Job <span style={{ fontFamily: 'monospace' }}>#{a.job_id}</span> · {a.crop_name} {a.variety ? `(${a.variety})` : ''} · Status: {a.job_status}
                  </div>

                  {/* After the job ref div inside expanded section */}
{a.is_split && a.splits?.length > 1 && (
  <div style={{ 
    marginBottom: '8px', padding: '8px 10px', 
    background: '#faf5ff', borderRadius: '8px',
    border: '1px solid #e9d5ff'
  }}>
    <div style={{ fontSize: '0.65rem', fontWeight: 700, color: '#7c3aed', marginBottom: '4px' }}>
      🔀 Split into {a.splits.length} parts
    </div>
    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
      {a.splits.map((s: any, i: number) => (
        <div key={i} style={{
          fontSize: '0.62rem', padding: '3px 8px', borderRadius: '6px',
          background: '#fff', border: '1px solid #e9d5ff', color: '#6b7280'
        }}>
          <span style={{ fontWeight: 600, color: '#7c3aed' }}>Part {i + 1}</span>
          {' · '}{s.total_area} ac
          {' · '}<span style={{
            color: s.allocation_status === 'pending' ? '#dc2626' : '#15803d'
          }}>{s.allocation_status}</span>
          {s.scheduled_date && ` · ${s.scheduled_date}`}
          {' · '}👷 {s.allocation_count} alloc{s.allocation_count !== 1 ? 's' : ''}
        </div>
      ))}
    </div>
  </div>
)}

                  {a.allocation_count === 0 ? (
                    <div style={{ fontSize: '0.78rem', color: '#9ca3af', padding: '8px' }}>
                      ⚠ No allocations yet for this activity
                    </div>
                  ) : (a.allocations || []).map((alloc: any, i: number) => {
                    const isDone = alloc.work_status === 'completed';
                    return (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap',
                        padding: '8px 12px', marginBottom: '4px', borderRadius: '8px',
                        background: isDone ? '#f0fdf4' : '#fff',
                        border: `1px solid ${isDone ? '#bbf7d0' : '#e5e7eb'}`,
                        fontSize: '0.72rem',
                      }}>
                        {/* Mukkadam */}
                        <div style={{ minWidth: '130px' }}>
                          <div style={{ fontWeight: 700, color: '#111827' }}>👷 {alloc.mukkadam_name}</div>
                          {alloc.mukkadam_mobile && (
                            <div style={{ fontSize: '0.62rem', color: '#9ca3af' }}>📞 {alloc.mukkadam_mobile}</div>
                          )}
                        </div>
                        {/* Cluster */}
                        {alloc.cluster_name && (
                          <span style={{ fontSize: '0.65rem', background: '#eff6ff', color: '#1d4ed8', padding: '1px 7px', borderRadius: '999px' }}>
                            🏘 {alloc.cluster_name}
                          </span>
                        )}
                        {/* Dates */}
                        <div>
                          <div style={{ color: '#6b7280' }}>📅 Allocated: {alloc.allocated_date || '—'}</div>
                        </div>
                        {/* Area */}
                        <div>
                          <div style={{ color: '#0f766e' }}>🌾 {alloc.allocated_area} ac allocated</div>
                          {alloc.actual_area_done != null && (
                            <div style={{ color: '#15803d', fontSize: '0.65rem' }}>✓ {alloc.actual_area_done} ac actual</div>
                          )}
                        </div>
                        {/* Workers */}
                        <div>
                          <div style={{ color: '#6b7280' }}>👥 {alloc.allocated_workers} workers</div>
                          {alloc.actual_crew_size != null && (
                            <div style={{ color: '#374151', fontSize: '0.65rem' }}>✓ {alloc.actual_crew_size} actual</div>
                          )}
                        </div>
                        {/* Rate + payment */}
                        <div>
                          <div style={{ color: '#7c3aed', fontWeight: 600 }}>
                            ₹{alloc.mukkadam_rate}/ac → ₹{Math.round(alloc.mukkadam_est).toLocaleString('en-IN')}
                          </div>
                          <div style={{ fontSize: '0.62rem', color: '#6b7280' }}>
                            Farmer rate: ₹{alloc.farmer_rate}/ac
                          </div>
                        </div>
                        {/* Status badges */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span style={{
                            fontSize: '0.6rem', padding: '1px 7px', borderRadius: '999px', fontWeight: 600,
                            background: isDone ? '#dcfce7' : alloc.work_status === 'in_progress' ? '#dbeafe' : '#f3f4f6',
                            color:      isDone ? '#15803d' : alloc.work_status === 'in_progress' ? '#1d4ed8' : '#6b7280',
                          }}>{alloc.work_status}</span>
                          {alloc.report_submitted && (
                            <span style={{ fontSize: '0.6rem', color: '#0369a1' }}>📋 Report submitted</span>
                          )}
                          {alloc.farmer_agreed === true  && <span style={{ fontSize: '0.6rem', color: '#15803d' }}>✅ Farmer agreed</span>}
                          {alloc.farmer_agreed === false && <span style={{ fontSize: '0.6rem', color: '#dc2626' }}>❌ Farmer disputed</span>}
                        </div>

                        {/* Mark Complete */}
                        {!isDone && isAdmin && (
                          <button
                            onClick={() => {
                              if (confirm(`Mark ${alloc.mukkadam_name}'s allocation as complete?`)) {
                                handleUpdownComplete(alloc.mukkadam_id, alloc.allocation_id);
                              }
                            }}
                            style={{
                              marginLeft: 'auto', padding: '4px 12px', borderRadius: '7px',
                              border: 'none', background: '#16a34a', color: '#fff',
                              fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer',
                            }}
                          >
                            ✅ Mark Complete
                          </button>
                        )}
                        {isDone && (
                          <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: '#15803d', fontWeight: 700 }}>✅ Done</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    )}
  </div>

  ) : tab === 'global' ? (
    <GlobalInsightsPanel />
  ) : (
    <></>
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
type MukkadamType = 'permanent' | 'updown';
type UpdownMode = 'range' | 'specific';

function AddToClusterModalM({
  mukkadam,
  cluster,
  onConfirm,
  onCancel,
  saving,
  isEdit,
}: {
  mukkadam: Mukkadam;
  cluster: ClusterOption;
  onConfirm: (
    transportPrice: number,
    weeklyPaymentDay: number,
    advanceAmount: number,
    weeklyAmount: number,
    updownConfig: {
      mukkadam_type: MukkadamType;
      updown_mode?: UpdownMode;
      updown_from_date?: string;
      updown_to_date?: string;
      updown_specific_dates?: string[];
    }
  ) => void;
  onCancel: () => void;
  saving: boolean;
  isEdit: boolean;
}) {
  const [transportPrice, setTransportPrice] = useState(
    cluster.transport_price != null ? String(cluster.transport_price) : ''
  );
  const [weeklyPaymentDay, setWeeklyPaymentDay] = useState<number>(
    cluster.weekly_payment_day ?? 0
  );
  const [advanceAmount, setAdvanceAmount] = useState(
    cluster.advance_amount != null
      ? String(cluster.advance_amount)
      : String(getAdvanceAmount(mukkadam.crew_size ?? 0))
  );
  const [weeklyAmount, setWeeklyAmount] = useState(
    cluster.weekly_amount != null
      ? String(cluster.weekly_amount)
      : String(getWeeklyAmount(mukkadam.crew_size ?? 0))
  );

  const [mukkadamType, setMukkadamType] = useState<MukkadamType>(
    cluster.mukkadam_type || 'permanent'
  );
  const [updownMode, setUpdownMode] = useState<UpdownMode>(
    cluster.updown_mode || 'range'
  );
  const [updownFrom, setUpdownFrom] = useState(cluster.updown_from_date || '');
  const [updownTo, setUpdownTo] = useState(cluster.updown_to_date || '');
  const [updownDates, setUpdownDates] = useState<string[]>(
    cluster.updown_specific_dates || []
  );
  const [updownDateInput, setUpdownDateInput] = useState('');

  const handleSubmit = () => {
    const price = parseFloat(transportPrice);
    const advance = parseFloat(advanceAmount);
    const weekly = parseFloat(weeklyAmount);

    if (isNaN(price) || price < 0) {
      toast.error('Enter a valid transport price');
      return;
    }
    if (isNaN(advance) || advance < 0) {
      toast.error('Enter a valid advance amount');
      return;
    }
    if (isNaN(weekly) || weekly < 0) {
      toast.error('Enter a valid weekly payment');
      return;
    }

    if (mukkadamType === 'updown') {
      if (updownMode === 'range') {
        if (!updownFrom || !updownTo) {
          toast.error('Set from and to dates');
          return;
        }
        if (updownFrom > updownTo) {
          toast.error('From date must be before to date');
          return;
        }
      }
      if (updownMode === 'specific' && updownDates.length === 0) {
        toast.error('Add at least one date');
        return;
      }
    }

    onConfirm(price, weeklyPaymentDay, advance, weekly, {
      mukkadam_type: mukkadamType,
      updown_mode: mukkadamType === 'updown' ? updownMode : undefined,
      updown_from_date:
        mukkadamType === 'updown' && updownMode === 'range'
          ? updownFrom
          : undefined,
      updown_to_date:
        mukkadamType === 'updown' && updownMode === 'range'
          ? updownTo
          : undefined,
      updown_specific_dates:
        mukkadamType === 'updown' && updownMode === 'specific'
          ? updownDates
          : undefined,
    });
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 10px',
    borderRadius: '7px',
    border: '1.5px solid #e5e7eb',
    fontSize: '0.88rem',
    outline: 'none',
    boxSizing: 'border-box',
  };

  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          borderRadius: '12px',
          padding: '24px',
          width: '400px',
          maxHeight: '90vh',
          overflowY: 'auto',
          boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
        }}
      >
        {/* Header */}
        <div style={{ marginBottom: '16px' }}>
          <h3
            style={{
              margin: 0,
              fontSize: '1rem',
              fontWeight: 700,
              color: '#111827',
            }}
          >
            {isEdit ? 'Edit in ' : 'Add to '}
            {cluster.name}
          </h3>
          <p
            style={{
              margin: '4px 0 0',
              fontSize: '0.82rem',
              color: '#6b7280',
            }}
          >
            {mukkadam.name} · Crew size: {mukkadam.crew_size ?? '—'}
          </p>
        </div>

        {/* ── TYPE TOGGLE ── */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '6px' }}>
            Type
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            {(['permanent', 'updown'] as const).map(t => (
              <button
                key={t}
                type="button"
                onClick={() => setMukkadamType(t)}
                style={{
                  flex: 1, padding: '8px', borderRadius: '8px',
                  fontSize: '0.82rem', fontWeight: 700, cursor: 'pointer',
                  border: `1.5px solid ${mukkadamType === t ? '#14b8a6' : '#e5e7eb'}`,
                  background: mukkadamType === t ? '#f0fdfa' : '#fff',
                  color: mukkadamType === t ? '#0f766e' : '#9ca3af',
                  transition: 'all 0.15s',
                }}
              >
                {t === 'permanent' ? '🏠 Permanent' : '📅 Updown'}
              </button>
            ))}
          </div>
        </div>

        {/* ── UPDOWN CONFIG ── */}
        {mukkadamType === 'updown' && (
          <div style={{
            background: '#fff7ed', border: '1px solid #fed7aa',
            borderRadius: '8px', padding: '12px 14px', marginBottom: '16px',
          }}>
            <p style={{
              margin: '0 0 10px', fontSize: '0.72rem', fontWeight: 700,
              color: '#c2410c', textTransform: 'uppercase', letterSpacing: '0.04em',
            }}>
              Updown Availability
            </p>

            {/* Mode toggle */}
            <div style={{ display: 'flex', gap: '6px', marginBottom: '12px' }}>
              {(['range', 'specific'] as const).map(mode => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setUpdownMode(mode)}
                  style={{
                    flex: 1, padding: '6px', borderRadius: '6px',
                    fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                    border: `1.5px solid ${updownMode === mode ? '#f97316' : '#e5e7eb'}`,
                    background: updownMode === mode ? '#fff7ed' : '#fff',
                    color: updownMode === mode ? '#c2410c' : '#9ca3af',
                    transition: 'all 0.15s',
                  }}
                >
                  {mode === 'range' ? '📆 Date Range' : '🗓 Specific Dates'}
                </button>
              ))}
            </div>

            {/* Range mode */}
            {updownMode === 'range' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ fontSize: '0.72rem', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '3px' }}>
                    From <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <input
                    type="date"
                    value={updownFrom}
                    onChange={e => setUpdownFrom(e.target.value)}
                    style={{ ...inputStyle, fontSize: '0.82rem' }}
                    onFocus={e => (e.currentTarget.style.borderColor = '#f97316')}
                    onBlur={e => (e.currentTarget.style.borderColor = '#e5e7eb')}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.72rem', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '3px' }}>
                    To <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <input
                    type="date"
                    value={updownTo}
                    onChange={e => setUpdownTo(e.target.value)}
                    style={{ ...inputStyle, fontSize: '0.82rem' }}
                    onFocus={e => (e.currentTarget.style.borderColor = '#f97316')}
                    onBlur={e => (e.currentTarget.style.borderColor = '#e5e7eb')}
                  />
                </div>
              </div>
            )}

            {/* Specific dates mode */}
            {updownMode === 'specific' && (
              <div>
                <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
                  <input
                    type="date"
                    value={updownDateInput}
                    onChange={e => setUpdownDateInput(e.target.value)}
                    style={{ ...inputStyle, flex: 1, fontSize: '0.82rem' }}
                    onFocus={e => (e.currentTarget.style.borderColor = '#f97316')}
                    onBlur={e => (e.currentTarget.style.borderColor = '#e5e7eb')}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (updownDateInput && !updownDates.includes(updownDateInput)) {
                        setUpdownDates(prev => [...prev, updownDateInput].sort());
                        setUpdownDateInput('');
                      }
                    }}
                    style={{
                      padding: '8px 14px', borderRadius: '7px', border: 'none',
                      background: '#f97316', color: '#fff',
                      fontSize: '0.82rem', fontWeight: 700, cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    + Add
                  </button>
                </div>
                {updownDates.length === 0 ? (
                  <p style={{ fontSize: '0.75rem', color: '#9ca3af', textAlign: 'center', margin: '4px 0' }}>
                    No dates added yet
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                    {updownDates.map(d => (
                      <span key={d} style={{
                        display: 'inline-flex', alignItems: 'center', gap: '4px',
                        padding: '3px 8px', borderRadius: '999px',
                        background: '#fed7aa', color: '#c2410c',
                        fontSize: '0.72rem', fontWeight: 600,
                      }}>
                        {d}
                        <button
                          type="button"
                          onClick={() => setUpdownDates(prev => prev.filter(x => x !== d))}
                          style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: '#c2410c', padding: 0, lineHeight: 1, fontSize: '0.75rem',
                          }}
                        >✕</button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── PAYMENT CONFIG ── */}
        <div style={{
          background: '#f0fdfa', border: '1px solid #99f6e4',
          borderRadius: '8px', padding: '12px 14px', marginBottom: '14px',
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
                type="number" min="0" value={advanceAmount}
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
                type="number" min="0" value={weeklyAmount}
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
            autoFocus type="number" min="0"
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
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            style={{
              flex: 1,
              padding: '9px',
              borderRadius: '7px',
              border: '1.5px solid #e5e7eb',
              background: '#fff',
              color: '#6b7280',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving || !transportPrice}
            style={{
              flex: 1,
              padding: '9px',
              borderRadius: '7px',
              border: 'none',
              background: saving ? '#99f6e4' : '#14b8a6',
              color: '#fff',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: saving ? 'not-allowed' : 'pointer',
            }}
          >
            {saving ? (isEdit ? 'Updating...' : 'Adding...') : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}
// ─── Mukkadam Add to Cluster Trigger ────────────────────

type MukkadamAddMode = 'add' | 'edit';

function MukkadamAddToCluster({
  mukkadam,
  clusters,
  onSuccess,
  mode,
  clusterToEdit,
}: {
  mukkadam: Mukkadam;
  clusters: ClusterOption[];
  onSuccess: () => void;
  mode: MukkadamAddMode;
  clusterToEdit?: ClusterOption; // required for edit
}) {
  const [openDropdown, setOpenDropdown] = useState(false);
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState<ClusterOption | null>(
    null
  );
  const btnRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // Edit mode: when clusterToEdit changes, open modal
  // useEffect(() => {
  //   if (mode === 'edit' && clusterToEdit) {
  //     setSelectedCluster(clusterToEdit);
  //   }
  // }, [mode, clusterToEdit]);

  const filtered = clusters.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const alreadyInCluster = (clusterId: number) =>
    mukkadam.clusters.some((c) => c.id === clusterId);


  const alreadyInClusterPermanently = (clusterId: number) =>
  mukkadam.clusters.some((c) => c.id === clusterId && c.mukkadam_type === 'permanent');

  const handleClusterSelect = (cluster: ClusterOption) => {
    if (saving) return;
    setOpenDropdown(false);
    setSearch('');
    setSelectedCluster(cluster);
  };

const handleConfirm = async (
  transportPrice: number,
  weeklyPaymentDay: number,
  advanceAmount: number,
  weeklyAmount: number,
  updownConfig: {
    mukkadam_type: MukkadamType;
    updown_mode?: UpdownMode;
    updown_from_date?: string;
    updown_to_date?: string;
    updown_specific_dates?: string[];
  }
) => {
  if (!selectedCluster) return;
  setSaving(true);
  try {
    const isEdit = mode === 'edit';
    const url = isEdit
      ? `${API_BASE_URL}/api/clusters/${selectedCluster.id}/update_mukkadam/`
      : `${API_BASE_URL}/api/cluster/${selectedCluster.id}/add_mukkadam/`;
    const method = isEdit ? 'PATCH' : 'POST';

    const token = localStorage.getItem('auth_token');

    const res = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Token ${token}` } : {}),
      },
      body: JSON.stringify({
        mukkadam_id: mukkadam.id,
        transport_price: transportPrice,
        weekly_payment_day: weeklyPaymentDay,
        advance_amount: advanceAmount,
        weekly_amount: weeklyAmount,
        mukkadam_type: updownConfig.mukkadam_type,
        updown_mode: updownConfig.updown_mode,
        updown_from_date: updownConfig.updown_from_date,
        updown_to_date: updownConfig.updown_to_date,
        updown_specific_dates: updownConfig.updown_specific_dates,
      }),
    });

    let data: any = null;
    try {
      data = await res.json();
    } catch (e) {
      console.error('Failed to parse JSON', e);
    }

    if (res.ok) {
      toast.success(
        data?.message ||
          (isEdit
            ? `Updated ${mukkadam.name} in ${selectedCluster.name}`
            : `${mukkadam.name} → ${selectedCluster.name}`),
      );
      setSelectedCluster(null);
      onSuccess();
    } else {
  console.error('Update error', res.status, data);
  const msg =
    data?.detail ||
    data?.error ||
    data?.message ||           // ← add this
    JSON.stringify(data) ||    // ← add this as last fallback
    `Failed to save mukkadam assignment (HTTP ${res.status})`;
  toast.error(msg);
}
  } catch (e) {
    console.error('Network error', e);
    toast.error('Network error');
  } finally {
    setSaving(false);
  }
};


  useEffect(() => {
    if (openDropdown) {
      setTimeout(() => {
        searchRef.current?.focus({ preventScroll: true });
      }, 0);
    }
  }, [openDropdown]);

  return (
    <>
      {mode === 'add' && (
        <div
          style={{ position: 'relative', display: 'inline-block' }}
          onClick={(e) => {
            e.stopPropagation();
            e.preventDefault();
          }}
        >
          <button
            type="button"
            ref={btnRef}
            onClick={() => setOpenDropdown((v) => !v)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '3px 10px 3px 8px',
              borderRadius: '999px',
              border: `1.5px solid ${openDropdown ? '#14b8a6' : '#d1d5db'}`,
              background: openDropdown ? '#f0fdfa' : '#fff',
              color: openDropdown ? '#0f766e' : '#6b7280',
              fontSize: '0.72rem',
              fontWeight: 600,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s',
            }}
          >
            <PlusCircle size={12} />
            Add to Cluster
          </button>

          {openDropdown && (
            <PortalDropdown
              anchorRef={btnRef as React.RefObject<HTMLElement>}
              onClose={() => {
                setOpenDropdown(false);
                setSearch('');
              }}
            >
              <DropdownHeader label="Add mukkadam to" />
              <div
                style={{
                  padding: '8px 10px',
                  borderBottom: '1px solid #f3f4f6',
                }}
              >
                <input
                  ref={searchRef}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search clusters..."
                  style={{
                    width: '100%',
                    padding: '5px 9px',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  onFocus={(e) =>
                    (e.currentTarget.style.borderColor = '#14b8a6')
                  }
                  onBlur={(e) =>
                    (e.currentTarget.style.borderColor = '#e5e7eb')
                  }
                />
              </div>
              <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                {filtered.length === 0 ? (
                  <p
                    style={{
                      padding: '12px',
                      textAlign: 'center',
                      fontSize: '0.8rem',
                      color: '#9ca3af',
                      margin: 0,
                    }}
                  >
                    No clusters found
                  </p>
                ) : (
                  filtered.map((c) => (
                    <ClusterItem
                      key={c.id}
                      name={c.name}
                      alreadyIn={alreadyInClusterPermanently(c.id)}
                      saving={saving}
                      onClick={() => handleClusterSelect(c)}
                    />
                  ))
                )}
              </div>
            </PortalDropdown>
          )}
        </div>
      )}

      {mode === 'edit' && (
  <button
    type="button"
    onClick={(e) => {
      e.stopPropagation();
      e.preventDefault();
      if (clusterToEdit) {
        setSelectedCluster(clusterToEdit);   // modal opens only when user clicks ✎
      }
    }}
    style={{ marginLeft: 4, border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '0.7rem', color: '#6b7280' }}
    title="Edit assignment"
  >
    ✎
  </button>
)}


      {selectedCluster && (
        <AddToClusterModalM
          mukkadam={mukkadam}
          cluster={selectedCluster}
          onConfirm={handleConfirm}
          onCancel={() => setSelectedCluster(null)}
          saving={saving}
          isEdit={mode === 'edit'}
        />
      )}
    </>
  );
}





































































































