

// pages/TenderDashboard.tsx
import React, { useCallback, useEffect,useMemo,useRef, useState } from "react";
import axios from "axios";
import {Pencil,Pen,Check,X,
  Users, Briefcase, ChevronDown, ChevronUp,
  MapPin, Phone, Calendar, Layers, IndianRupee,
  TrendingUp, RefreshCw, Filter, Search, CheckCircle,
  Clock, AlertCircle, Building2, User, PlusCircle
} from "lucide-react";
import { useNavigate } from 'react-router-dom';
import { JobNoteModal } from "./components/JobNoteModel";
import { AddToClusterModal, Cluster, CreateClusterModal, EditClusterModal, StateOption } from "./Tender";
import { API_BASE_URL } from "./types/config";
// const API_BASE = "http://localhost:8002/tender";
// const API_BASE_URL = "http://localhost:8002/tender";

import toast from "react-hot-toast";
import Dialpad from "./call";
// ─── Types ───────────────────────────────────────────────
// interface Activity { name: string; price: string; }


function CompleteAllocationsButton({ allocations, activityName, farmerName, onSuccess }: {
  allocations: any[];
  activityName: string;
  farmerName: string;
  onSuccess: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // Only show for allocations not yet completed
  const pending = allocations.filter(
    (al: any) => al.work_status !== 'completed',
  );

  if (pending.length === 0) return null;

  const handleConfirm = async () => {
    setSaving(true);
    const token = localStorage.getItem('auth_token');
    try {
      // Mark all pending allocations complete in parallel
      const results = await Promise.all(
        pending.map((al: any) =>
          fetch(`${API_BASE_URL}/api/allocations/${al.allocation_id}/mark_complete/`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Token ${token}`,
            },
          }).then(r => r.json()),
        ),
      );
      const allOk = results.every((r: any) => r.success);
      if (allOk) {
        toast.success(`✅ ${pending.length} allocation${pending.length > 1 ? 's' : ''} marked complete`);
        setConfirmOpen(false);
        onSuccess();
      } else {
        toast.error('Some allocations failed to update');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setConfirmOpen(true)}
        style={{ padding: '5px 12px', borderRadius: 8, background: 'linear-gradient(135deg,#059669,#047857)', color: '#fff', border: 'none', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
      >
        ✓ Complete
      </button>

      {confirmOpen && ReactDOM.createPortal(
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 999999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => setConfirmOpen(false)}
        >
          <div
            style={{ background: '#fff', borderRadius: 16, padding: 24, width: 360, boxShadow: '0 20px 60px rgba(0,0,0,.25)' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ fontWeight: 700, fontSize: 15, color: '#111827', marginBottom: 4 }}>
              Mark as Complete?
            </div>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 16 }}>
              {activityName} · {farmerName}
            </div>

            {/* Allocation summary */}
            <div style={{ background: '#f9fafb', borderRadius: 10, padding: 12, marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.7px', color: '#9ca3af', marginBottom: 8 }}>
                Allocations to complete
              </div>
              {pending.map((al: any, i: number) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderTop: i > 0 ? '1px solid #f3f4f6' : 'none' }}>
                  <span style={{ fontWeight: 600, color: '#374151' }}>👷 {al.mukkadam_name}</span>
                  <span style={{ color: '#6b7280' }}>{Number(al.allocated_area).toFixed(2)} ac · {al.allocated_date}</span>
                </div>
              ))}
            </div>

            <div style={{ fontSize: 11, color: '#f59e0b', background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: 8, padding: '8px 12px', marginBottom: 16 }}>
              ⚠️ This will mark work_status = completed. The mukkadam should ideally submit a day-end report first.
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setConfirmOpen(false)}
                style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={saving}
                style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: saving ? '#86efac' : '#059669', color: '#fff', fontSize: 12, fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}
              >
                {saving ? 'Saving...' : `✓ Confirm Complete`}
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
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
// ─────────────────────────────────────────────────────────────────────────────
// SHARED STYLE TOKENS  (copy once near top of file, outside components)
// ─────────────────────────────────────────────────────────────────────────────
const S = {
  // colours
  stone25:  '#fdfcfb', stone50: '#fafaf9', stone100: '#f5f5f4',
  stone200: '#e7e5e4', stone300: '#d6d3d1', stone400: '#a8a29e',
  stone500: '#78716c', stone600: '#57534e', stone700: '#44403c',
  stone800: '#292524', stone900: '#1c1917',
  brand:    '#059669', brandDark: '#047857', brandLight: '#ecfdf5',
  brandBorder: '#d1fae5',
  red50:'#fff1f2', red100:'#ffe4e6', red600:'#e11d48', red700:'#be123c',
  amber50:'#fffbeb', amber100:'#fef3c7', amber600:'#d97706', amber700:'#b45309',
  green50:'#ecfdf5', green100:'#d1fae5', green600:'#059669', green700:'#047857',
  sky50:'#f0f9ff', sky100:'#e0f2fe', sky600:'#0284c7', sky700:'#0369a1',
  violet50:'#f5f3ff', violet100:'#ede9fe', violet600:'#7c3aed', violet700:'#6d28d9',
  orange500:'#f97316',
  // shadows
  shadowCard: '0 0 0 1px rgba(28,25,23,.06),0 1px 3px rgba(28,25,23,.06),0 4px 12px rgba(28,25,23,.04)',
  shadowSm:   '0 1px 3px rgba(28,25,23,.07),0 1px 2px rgba(28,25,23,.04)',
  // fonts
  mono: "'JetBrains Mono','Fira Code',monospace",
  sans: "'DM Sans',-apple-system,BlinkMacSystemFont,sans-serif",
};
 
// helper: initials from name
const mkInitials = (name: string) =>
  name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
 
// avatar colour pairs (index by id hash)
const AV_COLORS = [
  { bg: S.sky50,    fg: S.sky700    },
  { bg: S.green50,  fg: S.green700  },
  { bg: S.violet50, fg: S.violet700 },
  { bg: S.amber50,  fg: S.amber700  },
  { bg: S.red50,    fg: S.red700    },
];
const avColor = (id: string | number) => {
  let h = 0;
  String(id).split('').forEach(c => { h = c.charCodeAt(0) + ((h << 5) - h); });
  return AV_COLORS[Math.abs(h) % AV_COLORS.length];
};
 
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
function MukkadamCard({ m, clusters, onSuccess, onCallClick, isAdmin = false }: {
  m: Mukkadam;
  clusters: ClusterOption[];
  onSuccess: () => void;
  onCallClick: (number: string) => void;
  isAdmin?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const av = avColor(m.id);
  const totalRate = (m.activity_rates || m.activities || []).reduce(
    (s: number, a: any) => s + Number(a.rate_per_acre ?? parseFloat(a.price || '0')), 0
  );
 
  /* ── row styles ── */
  const tdBase: React.CSSProperties = {
    padding: '10px 14px', borderBottom: expanded ? 'none' : `1px solid ${S.stone100}`,
    verticalAlign: 'middle', fontSize: 12,
  };
 
  return (
    <>
      {/* ── MAIN ROW ── */}
      <tr
        style={{ cursor: 'pointer', background: expanded ? S.brandLight : 'transparent', transition: 'background 150ms' }}
        onMouseEnter={e => { if (!expanded) (e.currentTarget as HTMLElement).style.background = S.stone25; }}
        onMouseLeave={e => { if (!expanded) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Mukkadam name */}
        <td style={{ ...tdBase, paddingLeft: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: av.bg, color: av.fg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 11, letterSpacing: '.3px' }}>
                {mkInitials(m.name)}
              </div>
              {m.clusters.length > 0 && (
                <div style={{ position: 'absolute', inset: -3, borderRadius: 13, border: `2px solid ${S.violet600}`, pointerEvents: 'none' }} />
              )}
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: '-.1px', color: S.stone900 }}>{m.name}</div>
              <div style={{ fontFamily: S.mono, fontSize: 10, color: S.stone400, marginTop: 2 }}>{m.mobile}</div>
            </div>
          </div>
        </td>
 
        {/* Location */}
        <td style={{ ...tdBase, color: S.stone600 }}>
          {m.location?.village}{m.location?.village && m.location?.district ? ', ' : ''}{m.location?.district}
        </td>
 
        {/* Crew */}
        <td style={{ ...tdBase, textAlign: 'center' }}>
          <span style={{ fontWeight: 700, color: S.violet600, fontSize: 13 }}>{m.crew_size}</span>
          <span style={{ color: S.stone400, fontSize: 12 }}>/{m.max_crew_capacity}</span>
        </td>
 
        {/* Activities count */}
        <td style={{ ...tdBase, textAlign: 'center', fontWeight: 700, fontSize: 13 }}>
          {(m.activity_rates || m.activities || []).length}
        </td>
 
        {/* Cluster pills */}
        <td style={{ ...tdBase }}>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
            {m.clusters.length === 0 ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: S.amber50, border: `1px solid ${S.amber100}`, color: S.amber700 }}>
                ⚠ No Cluster
              </span>
            ) : m.clusters.map((c: any) => (
              <span key={c.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: c.mukkadam_type === 'updown' ? '#fff7ed' : S.green50, color: c.mukkadam_type === 'updown' ? S.amber700 : S.green700, border: `1px solid ${c.mukkadam_type === 'updown' ? S.amber100 : S.green100}` }}>
                {c.mukkadam_type === 'updown' ? '📅' : '🏠'} {c.name}
                <MukkadamAddToCluster mukkadam={m} clusters={clusters} onSuccess={onSuccess} mode="edit" clusterToEdit={c} />
                {isAdmin && (
                  <button onClick={async e => {
                    e.stopPropagation();
                    if (!confirm(`Remove ${m.name} from "${c.name}"?`)) return;
                    const token = localStorage.getItem('auth_token');
                    await fetch(`${API_BASE_URL}/api/clusters/${c.id}/remove_mukkadam/`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Token ${token}` }, body: JSON.stringify({ mukkadam_id: m.id }) });
                    onSuccess();
                  }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', opacity: .7, fontSize: 11, padding: '0 2px', lineHeight: 1 }}
                    onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
                    onMouseLeave={e => (e.currentTarget.style.opacity = '.7')}
                  >✕</button>
                )}
              </span>
            ))}
            <div onClick={e => { e.stopPropagation(); e.preventDefault(); }}>
              <MukkadamAddToCluster mukkadam={m} clusters={clusters} onSuccess={onSuccess} mode="add" />
            </div>
          </div>
        </td>
 
        {/* Total rate */}
        <td style={{ ...tdBase, textAlign: 'right', fontFamily: S.mono, fontWeight: 700, fontSize: 12, color: S.green700 }}>
          ₹{totalRate.toLocaleString('en-IN')}
        </td>
 
        {/* Actions */}
        <td style={{ ...tdBase, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
            <button onClick={() => onCallClick(m.mobile)}
              style={{ padding: '5px 12px', borderRadius: 8, background: S.green50, color: S.green700, border: `1px solid ${S.green100}`, fontSize: 11, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
              📞 Call
            </button>
          </div>
        </td>
 
        {/* Chevron */}
        <td style={{ ...tdBase, textAlign: 'center', width: 44 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 8, border: `1px solid ${expanded ? S.brand : S.stone200}`, background: expanded ? S.brand : '#fff', color: expanded ? '#fff' : S.stone400, fontSize: 11, transition: 'all 250ms', transform: expanded ? 'rotate(180deg)' : 'none', boxShadow: expanded ? '0 2px 6px rgba(5,150,105,.3)' : 'none' }}>▾</div>
        </td>
      </tr>
 
      {/* ── EXPANDED DETAIL ROW ── */}
      {expanded && (
        <tr>
          <td colSpan={8} style={{ padding: 0, borderBottom: `1px solid ${S.stone200}`, background: S.stone25 }}>
            <div style={{ padding: '20px 24px' }}>
 
              {/* Stat strip */}
              <div style={{ display: 'flex', borderRadius: 14, overflow: 'hidden', background: '#fff', marginBottom: 16, boxShadow: S.shadowCard }}>
                {[
                  { val: <><span style={{ color: S.violet600, fontWeight: 800 }}>{m.crew_size}</span><span style={{ fontSize: 12, color: S.stone400, fontWeight: 500 }}>/{m.max_crew_capacity}</span></>, lbl: 'Crew Size' },
                  { val: (m.activity_rates || m.activities || []).length, lbl: 'Activities' },
                  { val: m.clusters.length > 0 ? m.clusters[0].name : <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: S.amber50, color: S.amber700, border: `1px solid ${S.amber100}` }}>No Cluster</span>, lbl: 'Cluster' },
                  { val: <span style={{ color: S.green600 }}>₹{totalRate.toLocaleString('en-IN')}</span>, lbl: 'Total Rate/ac' },
                  { val: m.efficiency ?? '0.15', lbl: 'Avg ac/worker' },
                ].map((s, i) => (
                  <div key={i} style={{ flex: 1, padding: '12px 14px', textAlign: 'center', borderRight: i < 4 ? `1px solid ${S.stone100}` : 'none', position: 'relative' }}>
                    <div style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)', width: 24, height: 2, borderRadius: 1, background: S.green100 }} />
                    <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-.3px', lineHeight: 1.3, marginTop: 4 }}>{s.val}</div>
                    <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.7px', color: S.stone400, marginTop: 3 }}>{s.lbl}</div>
                  </div>
                ))}
              </div>
 
              {/* Two-col body */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', background: '#fff', borderRadius: 14, boxShadow: S.shadowCard, overflow: 'hidden' }}>
 
                {/* Left: Activities & Rates */}
                <div style={{ padding: '16px 20px' }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 8, borderBottom: `1px solid ${S.stone100}` }}>
                    <span style={{ fontSize: 14 }}>📋</span> Activities &amp; Rates
                  </div>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        {['Activity', 'Price/ac', 'Efficiency'].map((h, i) => (
                          <th key={i} style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.5px', color: S.stone400, padding: '6px 0', textAlign: i === 0 ? 'left' : 'right', borderBottom: `2px solid ${S.stone200}` }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(m.activity_rates || m.activities || []).map((a: any, i: number) => (
                        <ActivityRowWithEfficiency key={a.rate_id ?? i} activity={a} mukkadamEfficiency={m.efficiency} />
                      ))}
                    </tbody>
                  </table>
                </div>
 
                {/* Right: Location */}
                <div style={{ padding: '16px 20px', borderLeft: `1px solid ${S.stone100}` }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 8, borderBottom: `1px solid ${S.stone100}` }}>
                    <span style={{ fontSize: 14 }}>📍</span> Location &amp; Availability
                  </div>
                  <div style={{ background: S.stone50, borderRadius: 10, padding: '10px 14px', border: `1px solid ${S.stone200}`, marginBottom: 14 }}>
                    {[
                      { k: 'Village', v: `${m.location?.village || '—'}, ${m.location?.taluka || '—'}` },
                      { k: 'District', v: `${m.location?.district || '—'}, ${m.location?.state || '—'}` },
                      { k: 'Status', v: <span style={{ color: S.green600 }}>● Available</span> },
                    ].map((r, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderTop: i > 0 ? `1px solid ${S.stone100}` : 'none' }}>
                        <span style={{ color: S.stone500 }}>{r.k}</span>
                        <span style={{ fontWeight: 600, color: S.stone800 }}>{r.v}</span>
                      </div>
                    ))}
                  </div>
                  {m.availability?.start_date && (
                    <div style={{ fontSize: 11, color: S.stone500, display: 'flex', alignItems: 'center', gap: 4 }}>
                      📅 {m.availability.start_date} → {m.availability.end_date || '?'}
                    </div>
                  )}
                  {m.reference_image_url && (
                    <>
                      <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, margin: '14px 0 8px', paddingTop: 12, borderTop: `1px solid ${S.stone100}` }}>🏷 Rate Card Reference</div>
                      <img src={m.reference_image_url} alt="Rate card"
                        style={{ borderRadius: 10, border: `1px solid ${S.stone200}`, width: '100%', maxHeight: 140, objectFit: 'cover', cursor: 'pointer' }}
                        onClick={() => window.open(m.reference_image_url, '_blank')} />
                    </>
                  )}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
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
import { useCurrentUser } from "./hooks/currentUser";
import ClusterActivityCalendar from "./ClusterCalender";
import FarmerBillingPage from "./components/FarmerBillPage";
import DayDetailModal from "./components/DayDetail";

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

 
// ─────────────────────────────────────────────────────────────────────────────
// FARMER CARD  — replace the whole existing FarmerCard function
// ─────────────────────────────────────────────────────────────────────────────
function FarmerCard({ farmer, clusters, onSuccess, isAdmin = false }: FarmerCardProps) {
  const [expanded, setExpanded]       = useState(false);
  const [expandedPlot, setExpandedPlot] = useState<number | null>(null);
 
  const av           = avColor(farmer.farmer_id);
  const inCluster    = countPlotsInCluster(farmer.plots_by_cluster);
  const prunDate     = getNearestPruningDate(farmer);
  const clusterStatus = classifyFarmer(farmer);
  const ringColor    = clusterStatus === 'full' ? S.brand : clusterStatus === 'partial' ? S.amber600 : 'transparent';
 
  const tdBase: React.CSSProperties = {
    padding: '10px 14px', borderBottom: expanded ? 'none' : `1px solid ${S.stone100}`,
    verticalAlign: 'middle', fontSize: 12,
  };
 
  return (
    <>
      {/* ── MAIN ROW ── */}
      <tr
        style={{ cursor: 'pointer', background: expanded ? S.brandLight : 'transparent', transition: 'background 150ms' }}
        onMouseEnter={e => { if (!expanded) (e.currentTarget as HTMLElement).style.background = S.stone25; }}
        onMouseLeave={e => { if (!expanded) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Farmer name */}
        <td style={{ ...tdBase, paddingLeft: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: av.bg, color: av.fg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 11, letterSpacing: '.3px' }}>
                {mkInitials(farmer.farmer_name)}
              </div>
              {ringColor !== 'transparent' && (
                <div style={{ position: 'absolute', inset: -3, borderRadius: 13, border: `2px solid ${ringColor}`, pointerEvents: 'none' }} />
              )}
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: '-.1px', color: S.stone900 }}>{farmer.farmer_name}</div>
              <div style={{ fontFamily: S.mono, fontSize: 10, color: S.stone400, marginTop: 2 }}>{farmer.phone_number}</div>
            </div>
          </div>
        </td>
 
        {/* Location */}
        <td style={{ ...tdBase, color: S.stone600 }}>{farmer.location || '—'}</td>
 
        {/* Plots */}
        <td style={{ ...tdBase, textAlign: 'center', fontWeight: 700, fontSize: 13 }}>{farmer.total_plots}</td>
 
        {/* Jobs */}
        <td style={{ ...tdBase, textAlign: 'center', fontWeight: 700, fontSize: 13 }}>{farmer.total_jobs}</td>
 
        {/* Cluster */}
        <td style={{ ...tdBase }}>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
            {farmer.clusters.length === 0 ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: S.amber50, border: `1px solid ${S.amber100}`, color: S.amber700 }}>⚠ No Cluster</span>
            ) : farmer.clusters.map(c => (
              <span key={c.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: S.green50, color: S.green700, border: `1px solid ${S.green100}` }}>
                {c.name}
                {isAdmin && (
                  <button onClick={async e => {
                    e.stopPropagation();
                    if (!confirm(`Remove ${farmer.farmer_name} from "${c.name}"?`)) return;
                    const token = localStorage.getItem('auth_token');
                    await fetch(`${API_BASE_URL}/api/clusters/${c.id}/remove_farmer/`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Token ${token}` }, body: JSON.stringify({ farmer_id: farmer.farmer_id }) });
                    onSuccess();
                  }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', marginLeft: 2, fontSize: 10, padding: 0, lineHeight: 1 }}>✕</button>
                )}
              </span>
            ))}
          </div>
        </td>
 
        {/* Activities count */}
        <td style={{ ...tdBase, textAlign: 'center', fontWeight: 700, fontSize: 13 }}>
          {farmer.plots_by_cluster.reduce((s, g) => s + g.plots.reduce((ss, p) => ss + (p.jobs?.reduce((sss, j) => sss + (j.activities?.length || 0), 0) || 0), 0), 0)}
        </td>
 
        {/* Pruning */}
        <td style={{ ...tdBase }}>
          {prunDate ? formatPruningBadge(prunDate) : null}
        </td>
 
        {/* Actions */}
        <td style={{ ...tdBase, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', alignItems: 'center' }}>
            <AddToClusterTrigger farmer={farmer} clusters={clusters} onSuccess={onSuccess} />
          </div>
        </td>
 
        {/* Chevron */}
        <td style={{ ...tdBase, textAlign: 'center', width: 44 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 8, border: `1px solid ${expanded ? S.brand : S.stone200}`, background: expanded ? S.brand : '#fff', color: expanded ? '#fff' : S.stone400, fontSize: 11, transition: 'all 250ms', transform: expanded ? 'rotate(180deg)' : 'none', boxShadow: expanded ? '0 2px 6px rgba(5,150,105,.3)' : 'none' }}>▾</div>
        </td>
      </tr>
 
      {/* ── EXPANDED DETAIL ROW ── */}
      {expanded && (
        <tr>
          <td colSpan={9} style={{ padding: 0, borderBottom: `1px solid ${S.stone200}`, background: S.stone25 }}>
            <div style={{ padding: '20px 24px' }}>
 
              {/* Stat strip */}
              <div style={{ display: 'flex', borderRadius: 14, overflow: 'hidden', background: '#fff', marginBottom: 16, boxShadow: S.shadowCard }}>
                {[
                  { val: <span style={{ color: S.sky600 }}>{farmer.total_plots}</span>, lbl: 'Plots' },
                  { val: farmer.total_jobs, lbl: 'Jobs' },
                  { val: farmer.clusters.length > 0
                    ? <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: S.green50, color: S.green700, border: `1px solid ${S.green100}`, fontWeight: 700 }}>{farmer.clusters[0].name}</span>
                    : <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: S.amber50, color: S.amber700, border: `1px solid ${S.amber100}`, fontWeight: 700 }}>No Cluster</span>,
                    lbl: 'Cluster' },
                  { val: prunDate ? <><span style={{ fontSize: 16 }}>🌿</span></> : '—', lbl: prunDate ? prunDate.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'No pruning' },
                  { val: farmer.plots_by_cluster.reduce((s, g) => s + g.plots.reduce((ss, p) => ss + (p.jobs?.reduce((sss, j) => sss + (j.activities?.length || 0), 0) || 0), 0), 0), lbl: 'Activities' },
                ].map((s, i) => (
                  <div key={i} style={{ flex: 1, padding: '12px 14px', textAlign: 'center', borderRight: i < 4 ? `1px solid ${S.stone100}` : 'none', position: 'relative' }}>
                    <div style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)', width: 24, height: 2, borderRadius: 1, background: S.green100 }} />
                    <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-.3px', lineHeight: 1.3, marginTop: 4 }}>{s.val}</div>
                    <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.7px', color: S.stone400, marginTop: 3 }}>{s.lbl}</div>
                  </div>
                ))}
              </div>
 
              {/* Cluster coverage bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: '#fff', borderRadius: 10, marginBottom: 16, boxShadow: S.shadowSm }}>
                <div style={{ flex: 1, height: 6, background: S.stone200, borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ height: '100%', borderRadius: 3, background: 'linear-gradient(135deg,#059669 0%,#0d9488 100%)', width: `${Math.min((inCluster / Math.max(farmer.total_plots, 1)) * 100, 100)}%` }} />
                </div>
                <span style={{ fontSize: 11, fontWeight: 600, color: S.stone500, whiteSpace: 'nowrap' }}>{inCluster}/{farmer.total_plots} in cluster</span>
              </div>
 
              {/* Plots by cluster */}
              <div style={{ background: '#fff', borderRadius: 14, boxShadow: S.shadowCard, overflow: 'hidden' }}>
                {farmer.plots_by_cluster.map((cg, gi) => (
                  <div key={gi}>
                    {/* cluster section title */}
                    <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, padding: '12px 20px 8px', display: 'flex', alignItems: 'center', gap: 6, borderBottom: `1px solid ${S.stone100}`, background: S.stone50 }}>
                      <span style={{ fontSize: 14 }}>🏗</span> {cg.cluster_name}
                      <span style={{ marginLeft: 'auto', padding: '2px 8px', borderRadius: 999, background: '#fff', border: `1px solid ${S.stone200}`, color: S.stone600, fontWeight: 600, fontSize: 10 }}>{cg.plots.length} plot{cg.plots.length !== 1 ? 's' : ''}</span>
                    </div>
 
                    <div style={{ padding: '10px 20px' }}>
                      {cg.plots.map(plot => (
                        <div key={plot.plot_id} style={{ background: '#fff', borderRadius: 14, boxShadow: S.shadowSm, marginBottom: 10, overflow: 'hidden', border: `1px solid ${S.stone200}` }}>
                          {/* plot header */}
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderBottom: `1px solid ${S.stone100}`, background: 'linear-gradient(180deg,#fff 0%,#fdfcfb 100%)', cursor: 'pointer' }}
                            onClick={() => setExpandedPlot(expandedPlot === plot.plot_id ? null : plot.plot_id)}>
                            <div>
                              <div style={{ fontSize: 14, fontWeight: 800, letterSpacing: '-.2px' }}>Plot {plot.plot_code}</div>
                              <div style={{ fontSize: 11, color: S.stone500, marginTop: 1 }}>
                                {plot.area_acres} ac · {plot.crop_name}{plot.variety ? ` · ${plot.variety}` : ''}{plot.pruning_date ? ` · Pruning: ${plot.pruning_date}` : ''} · {plot.jobs?.reduce((t, j) => t + (j.activities?.length || 0), 0)} activities
                              </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div onClick={e => e.stopPropagation()}>
                                <PlotClusterControl plot={plot} clusterGroups={farmer.plots_by_cluster} clusters={clusters} farmerId={farmer.farmer_id} onSuccess={onSuccess} />
                              </div>
                              <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 24, height: 24, borderRadius: 6, border: `1px solid ${S.stone200}`, background: '#fff', fontSize: 10, color: S.stone400, transition: 'transform 200ms', transform: expandedPlot === plot.plot_id ? 'rotate(180deg)' : 'none' }}>▾</div>
                            </div>
                          </div>
 
                          {/* plot jobs expanded */}
                          {expandedPlot === plot.plot_id && (
                            <div style={{ padding: '10px 14px' }}>
                              {plot.jobs.length === 0 ? (
                                <p style={{ fontSize: 11, color: S.stone400, fontStyle: 'italic' }}>No tender jobs for this plot</p>
                              ) : plot.jobs.map(job => (
                                <div key={job.job_id} style={{ marginBottom: 8 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'linear-gradient(135deg,#f0f9ff 0%,#e0f2fe 100%)', borderRadius: 8, marginBottom: 6, border: `1px solid ${S.sky100}` }}>
    <span style={{ fontSize: 11, fontWeight: 700, color: S.sky700 }}>#{job.job_id}</span>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>  {/* 👈 wrap in div */}
      <span style={{ fontSize: 11, color: S.sky600 }}>{job.activities.length} activities</span>
      <CancelJobButton job={job} onSuccess={onSuccess} />  {/* 👈 add this */}
    </div>
  </div>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                    {job.activities.map(a => (
                                      <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 10px', borderRadius: 6, fontSize: 12, transition: 'background 150ms' }}
                                        onMouseEnter={e => (e.currentTarget.style.background = S.stone50)}
                                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                                        <div style={{ flex: 1, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.name}</div>
                                        <div style={{ fontFamily: S.mono, fontSize: 10, color: S.stone500, minWidth: 50, textAlign: 'right' }}>{a.total_area} ac</div>
                                        <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.4px', background: a.allocation_status === 'fully_allocated' || a.allocation_status === 'completed' ? S.green50 : a.allocation_status === 'partially_allocated' ? S.sky50 : S.amber50, color: a.allocation_status === 'fully_allocated' || a.allocation_status === 'completed' ? S.green700 : a.allocation_status === 'partially_allocated' ? S.sky700 : S.amber700 }}>
                                          {a.allocation_status === 'fully_allocated' ? 'Allocated' : a.allocation_status === 'partially_allocated' ? 'Partial' : a.allocation_status === 'completed' ? 'Done' : 'Pending'}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
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
 
            </div>
          </td>
        </tr>
      )}
    </>
  );
}


function CancelJobButton({ job, onSuccess }: { job: any; onSuccess: () => void }) {
  const [open, setOpen]       = useState(false);
  const [reason, setReason]   = useState('');
  const [cancelAllocs, setCancelAllocs] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const hasActiveAllocs = (job.activities ?? []).some((a: any) =>
    a.allocation_status !== 'pending' && a.allocation_status !== 'completed'
  );

  async function handleConfirm() {
    if (!reason.trim()) { setError('Reason is required'); return; }
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('auth_token')
      const res = await fetch(`${API_BASE_URL}/api/jobs/${job.job_id}/cancel/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json','Authorization':`Token ${token}` },
        body: JSON.stringify({ reason: reason.trim(), cancel_allocations: cancelAllocs }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to cancel job');
      setOpen(false);
      setReason('');
      setCancelAllocs(false);
      onSuccess();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        style={{ padding: '3px 10px', borderRadius: 6, background: '#fff1f2', color: '#be123c', border: '1px solid #fecaca', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
      >
        🚫 Cancel Job
      </button>

      {open && (
        <div
          onClick={() => !loading && setOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{ background: '#fff', borderRadius: 16, padding: 24, width: 440, boxShadow: '0 20px 60px rgba(0,0,0,0.2)', display: 'flex', flexDirection: 'column', gap: 16 }}
          >
            {/* Header */}
            <div>
              <div style={{ fontWeight: 800, fontSize: 16, color: '#be123c' }}>🚫 Cancel Job</div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                Job #{job.job_id} · {job.activities.length} activit{job.activities.length === 1 ? 'y' : 'ies'}
              </div>
            </div>

            {/* Activities preview */}
            <div style={{ background: '#f9fafb', borderRadius: 8, padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 140, overflowY: 'auto' }}>
              {job.activities.map((a: any) => (
                <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#374151' }}>
                  <span style={{ fontWeight: 500 }}>{a.name}</span>
                  <span style={{ color: '#9ca3af', fontFamily: 'monospace' }}>{a.total_area} ac · {a.allocation_status}</span>
                </div>
              ))}
            </div>

            {/* Reason */}
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: '#374151', display: 'block', marginBottom: 6 }}>
                Reason <span style={{ color: '#be123c' }}>*</span>
              </label>
              <textarea
                value={reason}
                onChange={e => { setReason(e.target.value); setError(''); }}
                placeholder="Why is this job being cancelled?"
                rows={3}
                style={{ width: '100%', borderRadius: 8, border: '1px solid #e5e7eb', padding: '8px 10px', fontSize: 12, fontFamily: 'inherit', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }}
              />
            </div>

            {/* Cancel allocations checkbox */}
            {hasActiveAllocs && (
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer', padding: '10px 12px', borderRadius: 10, background: cancelAllocs ? '#fff1f2' : '#f9fafb', border: `1px solid ${cancelAllocs ? '#fecaca' : '#e5e7eb'}`, transition: 'all 150ms' }}>
                <input
                  type="checkbox"
                  checked={cancelAllocs}
                  onChange={e => setCancelAllocs(e.target.checked)}
                  style={{ marginTop: 2, accentColor: '#be123c', width: 14, height: 14, flexShrink: 0 }}
                />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#374151' }}>Also cancel linked allocations</div>
                  <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
                    Active allocations across all activities will be cancelled. Completed ones will be kept.
                  </div>
                </div>
              </label>
            )}

            {/* Error */}
            {error && (
              <div style={{ fontSize: 11, color: '#be123c', padding: '8px 12px', background: '#fff1f2', borderRadius: 8, border: '1px solid #fecaca' }}>
                ⚠ {error}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => { setOpen(false); setReason(''); setError(''); setCancelAllocs(false); }}
                disabled={loading}
                style={{ padding: '7px 16px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', color: '#374151' }}
              >
                Keep
              </button>
              <button
                onClick={handleConfirm}
                disabled={loading || !reason.trim()}
                style={{ padding: '7px 16px', borderRadius: 8, border: 'none', background: loading || !reason.trim() ? '#fca5a5' : '#be123c', color: '#fff', fontSize: 12, fontWeight: 700, cursor: loading || !reason.trim() ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}
              >
                {loading ? 'Cancelling…' : 'Confirm Cancel'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function MoveJobButtonTender({ act, onSuccess }: {
  act: any;
  onSuccess: () => void;
}) {
  const MOVE_REASONS = [
    'Not strict job — can reschedule',
    'Easy farmer — farmer agreed to move',
  ];

  const [open, setOpen]           = useState(false);
const [moveDate, setMoveDate] = useState('');
const [moveArea, setMoveArea] = useState('');
const [moveReason, setMoveReason] = useState('');
const [moveSaving, setMoveSaving] = useState(false);
  const [saving, setSaving]       = useState(false);

  const handleSubmit = async () => {
    if (!moveDate)                              return toast.error('Select a date');
    if (!moveArea || moveArea <= 0)             return toast.error('Enter valid area');
    if (!moveReason.trim())                     return toast.error('Please provide a reason');
    if (moveArea > Number(act.remaining_area ?? act.total_area ?? 0))
                                                return toast.error('Exceeds remaining area');
    const token = localStorage.getItem('auth_token');
    setSaving(true);
    try {
      const actId = act.id ?? act.activity_id;
      const res = await fetch(`${API_BASE_URL}/api/job-activities/${actId}/move/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
        body: JSON.stringify({ new_date: moveDate, area: moveArea, reason: moveReason }),
      });
      if (res.ok) {
        toast.success('Job moved');
        setOpen(false);
        setMoveDate('');
        setMoveReason('');
        onSuccess();
      } else {
        const err = await res.json();
        toast.error(err.error || 'Failed to move job');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setSaving(false);
    }
  };

  const maxArea = Number(act.remaining_area ?? act.total_area ?? 0);

  return (
    <>
      <button
        onClick={() => {
          setMoveArea(maxArea);
          setMoveDate('');
          setMoveReason('');
          setOpen(true);
        }}
        className="px-3 py-1.5 bg-orange-50 text-orange-600 border border-orange-200 text-xs font-semibold rounded-lg hover:bg-orange-100 transition"
      >
        Move
      </button>

      {open && ReactDOM.createPortal(
        <div
          className="fixed inset-0 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.4)', zIndex: 99999 }}
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl p-6 w-80"
            onClick={e => e.stopPropagation()}
          >
            <h4 className="font-bold text-gray-900 mb-4">Move Job Activity</h4>

            <div className="space-y-4">

              {/* Date */}
              <div>
                <label className="text-xs font-semibold text-gray-600 block mb-1">New Date</label>
                <input
                  type="date"
                  value={moveDate}
                  onChange={e => setMoveDate(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                />
              </div>

              {/* Area */}
              <div>
                <label className="text-xs font-semibold text-gray-600 block mb-1">
                  Area to Move (ac)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={maxArea}
                  value={moveArea}
                  onChange={e => setMoveArea(parseFloat(e.target.value) || 0)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                />
                <p className="text-xs text-gray-400 mt-1">Max: {maxArea} ac (remaining)</p>
                {moveArea > maxArea && (
                  <p className="text-xs text-red-500 mt-1">⚠ Exceeds remaining area</p>
                )}
              </div>

              {/* Reason */}
              <div>
                <label className="text-xs font-semibold text-gray-600 block mb-2">
                  Reason <span className="text-red-400">*</span>
                </label>
                <div className="flex flex-col gap-2 mb-2">
                  {MOVE_REASONS.map(r => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setMoveReason(r)}
                      className={`text-left px-3 py-2 rounded-lg border text-xs font-medium transition ${
                        moveReason === r
                          ? 'bg-orange-50 border-orange-400 text-orange-700'
                          : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-orange-300 hover:bg-orange-50'
                      }`}
                    >
                      {moveReason === r ? '✓ ' : ''}{r}
                    </button>
                  ))}
                </div>
                <textarea
                  value={moveReason}
                  onChange={e => setMoveReason(e.target.value)}
                  placeholder="Or type a custom reason..."
                  rows={2}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none"
                />
                {!moveReason.trim() && (
                  <p className="text-xs text-red-400 mt-1">Reason is required</p>
                )}
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setOpen(false)}
                className="flex-1 px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={saving || !moveReason.trim() || moveArea > maxArea}
                className="flex-1 px-4 py-2 bg-orange-500 text-white rounded-lg text-sm font-bold hover:bg-orange-600 disabled:opacity-50 transition"
              >
                {saving ? 'Moving...' : 'Confirm Move'}
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
// ─── Main Page ───────────────────────────────────────────
export default function TenderDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
   const [expandedCluster, setExpandedCluster] = useState<number | null>(null);


   const [showInsightDayDetail, setShowInsightDayDetail] = useState(false);
const [insightDetailDate, setInsightDetailDate] = useState<Date | null>(null);
const [insightDetailCluster, setInsightDetailCluster] = useState<any | null>(null);


const [focusMukkadamId, setFocusMukkadamId] = useState<number | null>(null);
  const [paymentData, setPaymentData]         = useState<any>(null);
const [paymentLoading, setPaymentLoading]   = useState(false);
const [paymentFilter, setPaymentFilter]     = useState<string>('ready_to_bill');
const [paymentClusterFilter, setPaymentClusterFilter] = useState<string>('all');
const [paymentActivityFilter, setPaymentActivityFilter] = useState<string>('all');
const [paymentClusterSort, setPaymentClusterSort] = useState<string>('due');
const [expandedFarmerKey, setExpandedFarmerKey]   = useState<string | null>(null);
const [expandedFarmerData, setExpandedFarmerData] = useState<any>(null);
const [expandedFarmerLoading, setExpandedFarmerLoading] = useState(false);




const [jobNotes, setJobNotes]               = useState<Record<string, any[]>>({}); // jobId → notes[]
const [notesLoading, setNotesLoading]       = useState(false);

  const [farmerSubTab, setFarmerSubTab] = useState<'all' | 'full' | 'partial' | 'none' | 'new'>('all');
   const navigate = useNavigate();

   const [isAdmin, setIsAdmin] = useState(false);

const { user: currentUser } = useCurrentUser();
  const currentUserId   = currentUser?.id   ?? 0;
  const currentUserName = currentUser?.full_name ?? currentUser?.username ?? '';
   

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


const [insightDayAllocations, setInsightDayAllocations] = useState<any[]>([]);
const [insightDayMukkadams, setInsightDayMukkadams] = useState<any[]>([]);
const fetchInsightDayData = async (date: Date, clusterId: number) => {
  const dateStr = formatDateInsight(date);
  const token = localStorage.getItem('auth_token');

  try {
    const [allocRes, mukkRes] = await Promise.all([
      fetch(`${API_BASE_URL}/api/allocations/?allocated_date=${dateStr}&cluster_id=${clusterId}`, {
        headers: { Authorization: `Token ${token}` },
      }),
      fetch(`${API_BASE_URL}/api/mukkadams/daily_capacity_all/?date=${dateStr}&cluster_id=${clusterId}`, {
        headers: { Authorization: `Token ${token}` },
      }),
    ]);

    const allocData = await allocRes.json();
    const mukkData  = await mukkRes.json();

    setInsightDayAllocations(Array.isArray(allocData) ? allocData : allocData.results ?? []);
    setInsightDayMukkadams(Array.isArray(mukkData) ? mukkData : []);
  } catch (e) {
    console.error('Failed to fetch insight day data', e);
  }
};
  // Change the tab type
// change tab type
const [tab, setTab] = useState<'command' | 'calendar' |'global'| 'mukkadams' | 'farmers' | 'jobs' | 'payment'>('command');
// Command Center state
const [cmdClusters, setCmdClusters]         = useState<Cluster[]>([]);
const [cmdLoading, setCmdLoading]           = useState(false);
const [cmdSearch, setCmdSearch]             = useState('');
const [showCreateModal, setShowCreateModal] = useState(false);
const [editModal, setEditModal]             = useState<Cluster | null>(null);
const [cmdAddModal, setCmdAddModal]         = useState<{ clusterId: number; clusterName: string; mode: 'farmer' | 'mukkadam' } | null>(null);
const [calendarClusterId, setCalendarClusterId]   = useState<number | null>(null);
const [calendarClusterName, setCalendarClusterName] = useState('');
const [states, setStates]                   = useState<StateOption[]>([]);
  const [search, setSearch] = useState('');
  const [clusterFilter, setClusterFilter] = useState('');
  const [clusters, setClusters] = useState<ClusterOption[]>([]);
// Add alongside clusterFilter state
const [noCluster, setNoCluster] = useState(false);


const [dialpadOpen, setDialpadOpen] = useState(false);
const [dialpadNumber, setDialpadNumber] = useState('');
const [actTotalCount, setActTotalCount] = useState<number>(0);

const [cmdFilter, setCmdFilter] = useState<string>('all');
const [cmdRegion, setCmdRegion] = useState<string>('all');

const [pruningFrom, setPruningFrom] = useState('');
const [pruningTo, setPruningTo] = useState('');
  // ── AddToClusterModal state ──
  const [clusterModal, setClusterModal] = useState<{
    clusterId: number;
    clusterName: string;
    farmerId: string; // pre-selected farmer (future: pass to modal)
  } | null>(null);


  // Add this useEffect alongside your existing ones:
useEffect(() => {
  if (tab !== 'command') return;
  const load = async () => {
    setCmdLoading(true);
    try {
      const params = new URLSearchParams();
      if (cmdSearch.trim()) params.append('q', cmdSearch.trim());
      const res = await fetch(`${API_BASE_URL}/api/clusters/?${params.toString()}`);
      const data = await res.json();
      setCmdClusters(data);
    } finally {
      setCmdLoading(false);
    }
  };
  const id = setTimeout(load, 300);
  return () => clearTimeout(id);
}, [tab, cmdSearch]);

useEffect(() => {
  fetch(`${API_BASE_URL}/locations/states/`)
    .then(r => r.json())
    .then(setStates)
    .catch(() => {});
}, []);
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
const formatDateInsight = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
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
}, [actCluster, actDateFrom, actDateTo, actSearch, actSubTab]);


// Fetch notes for all loaded activities' job IDs
useEffect(() => {
  if (tab !== 'jobs' || activities.length === 0) return;

  const jobIds = [...new Set(activities.map((a: any) => a.job_id))];
  if (jobIds.length === 0) return;

  const token = localStorage.getItem('auth_token');
  setNotesLoading(true);

  // Fetch notes filtered by these job IDs
  // Use actCluster if set, otherwise fetch without cluster filter
  const cid = actCluster || '';
  const params = new URLSearchParams();
  if (cid) params.set('cluster_id', cid);
  // API supports job_ids as comma-separated or multiple params
  jobIds.forEach(id => params.append('job_id', id));

  fetch(`${API_BASE_URL}/api/job-notes/?${params.toString()}`, {
    headers: { Authorization: `Token ${token}` },
  })
    .then(r => r.json())
    .then((data: any[]) => {
      // Group by job_id
      const grouped: Record<string, any[]> = {};
      (Array.isArray(data) ? data : data.results ?? []).forEach((n: any) => {
        if (!grouped[n.job_id]) grouped[n.job_id] = [];
        grouped[n.job_id].push(n);
      });
      setJobNotes(grouped);
    })
    .catch(() => {})
    .finally(() => setNotesLoading(false));
}, [activities, tab, actCluster]);// ← allActivities REMOVED
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

// ── Jobs tab: allocation + move + note ───────────────────────────────────────
const [jobsHalfDayDialog, setJobsHalfDayDialog] = useState<{
  open: boolean;
  jobId: string;
  act: any;
  mukkadam: any;
  rate: any;
  availableWorkers: number;
  neededWorkers: number;
  remainingArea: number;
  isSecondJob: boolean;
  jobSlotsUsed: number;
  targetDate: string;
} | null>(null);
const [jobsAllowsMoreJobs, setJobsAllowsMoreJobs] = useState(false);
const [jobsNoteJobId, setJobsNoteJobId]     = useState<string | null>(null);
const [jobsNoteJobLabel, setJobsNoteJobLabel] = useState('');
// Add state if not already there:
const [showCalendar, setShowCalendar] = useState(false);
// per-activity availability — fetched once per activity click
const [jobsAvailableMukkadams, setJobsAvailableMukkadams] = useState<Map<string, any[]>>(new Map());
const [jobsMaxWorkRows, setJobsMaxWorkRows] = useState<any[]>([]);
const [jobsCapacityDate, setJobsCapacityDate] = useState<string | null>(null);
// ── Allocation dialog (jobs tab) ─────────────────────────────────────────────
const [allocDialog, setAllocDialog] = useState<{
  open: boolean;
  act: any;
  job: any;
  isoDate: string;
  mukkadams: any[];        // fetched on click
  loadingMukkadams: boolean;
} | null>(null);

const [allocHalfDay, setAllocHalfDay] = useState<{
  open: boolean;
  act: any;
  job: any;
  mukkadam: any;
  rate: any;
  availableWorkers: number;
  remainingArea: number;
  isoDate: string;
  jobSlotsUsed: number;
} | null>(null);
const [allocAllowsMore, setAllocAllowsMore] = useState(false);

// ── Move dialog (jobs tab) ───────────────────────────────────────────────────
const [moveDialog, setMoveDialog] = useState<{
  act: any;
  job: any;
} | null>(null);
const [moveDate, setMoveDate] = useState('');
const [moveReason, setMoveReason] = useState('');
const [moveSaving, setMoveSaving] = useState(false);

// ── Note modal (jobs tab) ────────────────────────────────────────────────────
const [noteDialog, setNoteDialog] = useState<{
  jobId: string;
  label: string;
} | null>(null);
const [noteText, setNoteText] = useState('');
const [noteSaving, setNoteSaving] = useState(false);
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



useEffect(() => {
  if (tab !== 'payment') return;
  setPaymentLoading(true);
  const token = localStorage.getItem('auth_token');
  fetch(`${API_BASE_URL}/api/payment-overview/`, {
    headers: { Authorization: `Token ${token}` },
  })
    .then(r => r.json())
    .then(setPaymentData)
    .catch(console.error)
    .finally(() => setPaymentLoading(false));
}, [tab]);


const handleExpandFarmer = async (farmer: any) => {
  const key = `${farmer.farmer_id}__${farmer.activity}`;
  if (expandedFarmerKey === key) {
    setExpandedFarmerKey(null);
    setExpandedFarmerData(null);
    return;
  }
  setExpandedFarmerKey(key);
  setExpandedFarmerData(null);
  if (!farmer.cluster_id) return;
  setExpandedFarmerLoading(true);
  const token = localStorage.getItem('auth_token');
  try {
    const res = await fetch(
      `${API_BASE_URL}/api/cluster/${farmer.cluster_id}/payment-dashboard/`,
      { headers: { Authorization: `Token ${token}` } }
    );
    const d = await res.json();
    const farmerDetail = (d.farmers ?? []).find(
      (f: any) => String(f.farmer_id) === String(farmer.farmer_id)
    );
    setExpandedFarmerData(farmerDetail ?? null);
  } catch (e) { console.error(e); }
  finally { setExpandedFarmerLoading(false); }
};

const handleConfirmAllocate = async () => {
  if (!allocHalfDay) return;
  const { act, job, mukkadam, rate, availableWorkers, remainingArea, isoDate, jobSlotsUsed } = allocHalfDay;
  const slotsUsed  = jobSlotsUsed ?? 0;
  const isLastSlot = slotsUsed >= 2;
  const isMidSlot  = slotsUsed === 1;
  const allowsMoreJobsToSend = isLastSlot ? false : isMidSlot ? true : allocAllowsMore;

  // Resolve cluster_id from activity's farmer_clusters, then plot clusters, then filter
  const resolvedClusterId =
    act?.farmer_clusters?.[0]?.id ??
    act?.clusters?.[0]?.id ??
    actCluster ??
    clusterFilter ??
    null;

  if (!resolvedClusterId) {
    toast.error('Cannot determine cluster for this activity. Add the farmer/plot to a cluster first.');
    return;
  }

  const token = localStorage.getItem('auth_token');
  try {
    const res = await fetch(`${API_BASE_URL}/api/allocations/create_allocation/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
      body: JSON.stringify({
        job_activity_id:   act.id ?? act.activity_id,
        mukkadam_id:       mukkadam.mukkadam_id,
        allocated_date:    isoDate,
        allocated_area:    remainingArea,
        allocated_workers: availableWorkers,
        farmer_rate:       act.rate_per_acre ?? 0,
        mukkadam_rate:     Number(rate?.rate_per_acre || 0),
        cluster_id:        resolvedClusterId,
        skip_strict_check: false,
        allows_second_job: allowsMoreJobsToSend,
        job_slot:          slotsUsed + 1,
      }),
    });

    // Log the actual error for debugging
    const d = await res.json();
    console.log('Allocation response:', res.status, d);

    if (res.ok) {
      const slotLabel = ['1st', '2nd', '3rd'][slotsUsed] ?? `${slotsUsed + 1}th`;
      toast.success(
        allowsMoreJobsToSend
          ? `✅ Allocated to ${mukkadam.mukkadam_name} (⅓ day – ${slotLabel} job)`
          : `✅ Allocated to ${mukkadam.mukkadam_name} (${slotLabel} job – day complete)`,
      );
      setAllocHalfDay(null);
      setAllocDialog(null);
      setAllocAllowsMore(false);
      fetchActivities(); // refresh the jobs list too
      fetchDataSilent();
    } else {
      // Show the actual backend error message
      toast.error(d.error || d.detail || d.message || JSON.stringify(d) || 'Allocation failed');
    }
  } catch (e) {
    console.error('Allocation error:', e);
    toast.error('Network error — check console');
  }
};
// ── Move job activity to a new date ──────────────────────────────────────────
const handleMoveJob = async () => {
  if (!moveDialog || !moveDate) return;
  if (!moveReason.trim()) { toast.error('Please provide a reason'); return; }
  const maxArea = Number(moveDialog.act.remaining_area ?? moveDialog.act.total_area ?? 0);
  const areaToMove = moveArea ? parseFloat(moveArea) : maxArea;
  if (isNaN(areaToMove) || areaToMove <= 0) { toast.error('Enter valid area'); return; }
  if (areaToMove > maxArea) { toast.error('Exceeds remaining area'); return; }

  setMoveSaving(true);
  const token = localStorage.getItem('auth_token');
  try {
    const actId = moveDialog.act.id ?? moveDialog.act.activity_id;
    const res = await fetch(`${API_BASE_URL}/api/job-activities/${actId}/move/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
      body: JSON.stringify({ new_date: moveDate, area: areaToMove, reason: moveReason }),
    });
    if (res.ok) {
      toast.success(`Moved to ${moveDate}`);
      setMoveDialog(null);
      setMoveDate('');
      setMoveArea('');
      setMoveReason('');
      fetchDataSilent();
    } else {
      const d = await res.json().catch(() => ({}));
      toast.error(d.error || 'Move failed');
    }
  } catch {
    toast.error('Move failed');
  } finally {
    setMoveSaving(false);
  }
};
// ── Save note ─────────────────────────────────────────────────────────────────
const handleSaveNote = async () => {
  if (!noteDialog || !noteText.trim()) return;
  setNoteSaving(true);
  const token = localStorage.getItem('auth_token');
  try {
    const res = await fetch(`${API_BASE_URL}/api/job-notes/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
      body: JSON.stringify({
        job_id:   noteDialog.jobId,
        text:     noteText.trim(),
        note_date: new Date().toISOString().slice(0, 10),
        tags:     [],
      }),
    });
    if (res.ok) {
      toast.success('Note saved');
      setNoteDialog(null);
      setNoteText('');
    } else {
      toast.error('Failed to save note');
    }
  } catch {
    toast.error('Failed to save note');
  } finally {
    setNoteSaving(false);
  }
};
// ── Fetch mukkadams capacity for a given date (jobs tab) ─────────────────────
const fetchJobsCapacity = async (isoDate: string, act?: any) => {
  if (jobsCapacityDate === isoDate) return; // already loaded for this date
  try {
    const token = localStorage.getItem('auth_token');
    // Use the farmer's own cluster — first one from farmer_clusters
    // Fallback chain: farmer_clusters[0] → act.clusters[0] → clusterFilter → clusterId
    const farmerClusterId =
      act?.farmer_clusters?.[0]?.id ??
      act?.clusters?.[0]?.id ??
      clusterFilter ??
      clusterId;
    const cid = farmerClusterId;
    const res = await fetch(
      `${API_BASE_URL}/api/mukkadams/daily_capacity_all/?date=${isoDate}&cluster_id=${cid}`,
      { headers: { Authorization: `Token ${token}` } },
    );
    const capacityData: any[] = await res.json();

                        // Deduplicate capacity by mukkadam_id, keep highest crew size
                        const capacityMap = new Map<number, number>();
                        capacityData.forEach((d: any) => {
                          const existing = capacityMap.get(d.mukkadam_id) ?? 0;
                          if (d.available_crew_size > existing) {
                            capacityMap.set(d.mukkadam_id, d.available_crew_size);
                          }
                        });

                        // Fetch mukkadam details (name, rates) from mukkadams API
                        const mukkadamIds = Array.from(capacityMap.keys());
                        let mukkadamDetails: any[] = [];
                        try {
                          const mukkRes = await fetch(
                            `${API_BASE_URL}/api/mukkadams/?cluster_id=${cid}`,
                            { headers: { Authorization: `Token ${token}` } },
                          );
                          const mukkData = await mukkRes.json();
                          // API may return array or { results: [] }
                          mukkadamDetails = Array.isArray(mukkData)
                            ? mukkData
                            : (mukkData.results ?? mukkData.mukkadams ?? []);
                        } catch {
                          // fallback to dashboard mukkadams if fetch fails
                          mukkadamDetails = data?.mukkadams ?? [];
                        }

                        // Build enriched list — only mukkadams with capacity today
                        const enriched = mukkadamIds.map(mukkadamId => {
                          const availCrew = capacityMap.get(mukkadamId) ?? 0;
                          const detail = mukkadamDetails.find(
                            (m: any) => m.mukkadam_id === mukkadamId,
                          );
                          const activityRates: any[] = detail?.activity_rates ?? [];
                          const matchedRate = activityRates.find((r: any) =>
                            r.activity_id === act.activity_id ||
                            r.activity_name === act.activity_name,
                          );
                          const productivity = Number(
                            matchedRate?.productivity_per_worker ?? 0.15,
                          );
                          const maxArea = availCrew * productivity;

                          return {
                            mukkadam_id:         mukkadamId,
                            mukkadam_name:       detail?.mukkadam_name ?? `Mukkadam #${mukkadamId}`,
                            mobile_numbers:      detail?.mobile_numbers ?? '—',
                            crew_size:           detail?.crew_size ?? availCrew,
                            available_crew_size: availCrew,
                            activity_rates:      activityRates,
                            max_area:            maxArea,
                            rate:                matchedRate,
                          };
                        }).filter(m => m.available_crew_size > 0); // exclude holidays

                        setAllocDialog(prev =>
                          prev ? { ...prev, mukkadams: enriched, loadingMukkadams: false } : prev,
                        );
    // Build maxWorkRows same way DayDetailModal does
    const usedWorkers = new Map<number, number>();
    // no allocations context here so start from 0 — will show full capacity
    const rows: any[] = [];
    capacityData.forEach((m: any) => {
      if ((m.available_crew_size ?? 0) <= 0) return;
      const remaining = m.available_crew_size ?? m.crew_size ?? 0;
      (m.activity_rates || []).forEach((rate: any) => {
        const productivity = Number(rate.productivity_per_worker || 0);
        if (!productivity) return;
        rows.push({
          mukkadamId:       m.mukkadam_id,
          mukkadamName:     m.mukkadam_name,
          mobileNumbers:    m.mobile_numbers,
          crewSize:         m.crew_size,
          activityId:       rate.activity_id,
          activityName:     rate.activity_name,
          productivity,
          availableWorkers: remaining,
          maxArea:          remaining * productivity,
          rate,
          mukkadamObj:      m,
        });
      });
    });

    setJobsMaxWorkRows(rows);
    setJobsCapacityDate(isoDate);
  } catch (e) {
    console.error('Failed to fetch jobs capacity', e);
  }
};


const [insightsData, setInsightsData]     = useState<any>(null);
const [insightsLoading, setInsightsLoading] = useState(false);
const [insightSort, setInsightSort]       = useState<'pending' | 'progress' | 'name'>('pending');
const [insightHover, setInsightHover]     = useState<number | null>(null);
const [paymentSubTab, setPaymentSubTab]           = useState<'farmer' | 'mukkadam'>('farmer');
const [mukkadamPayData, setMukkadamPayData]       = useState<any>(null);
const [mukkadamPayLoading, setMukkadamPayLoading] = useState(false);
const [mukkadamClusterId, setMukkadamClusterId]   = useState<number | null>(null);


useEffect(() => {
  if (tab !== 'payment' || paymentSubTab !== 'mukkadam') return;
  setMukkadamPayLoading(true);
  const token = localStorage.getItem('auth_token');
  fetch(`${API_BASE_URL}/api/mukkadam-payment-overview/`, {
    headers: { Authorization: `Token ${token}` },
  })
    .then(r => r.json())
    .then(setMukkadamPayData)
    .catch(console.error)
    .finally(() => setMukkadamPayLoading(false));
}, [tab, paymentSubTab]);

useEffect(() => {
  if (tab !== 'global') return;
  setInsightsLoading(true);
  if (allActivities.length === 0) {
    fetchActivities(); // 👈 fetch activities when global tab opens
  }
  const token = localStorage.getItem('auth_token');
  fetch(`${API_BASE_URL}/api/insights/`, {
    headers: { Authorization: `Token ${token}` },
  })
    .then(r => r.json())
    .then(setInsightsData)
    .catch(console.error)
    .finally(() => setInsightsLoading(false));
}, [tab]);
// ── Confirm ⅓-day allocation from Jobs tab ───────────────────────────────────
const handleJobsConfirmAllocation = async () => {
  if (!jobsHalfDayDialog) return;
  const { act, mukkadam, rate, availableWorkers, remainingArea, jobSlotsUsed, targetDate } = jobsHalfDayDialog;
  const slotsUsed = jobSlotsUsed ?? 0;
  const isLastSlot = slotsUsed >= 2;
  const isMidSlot  = slotsUsed === 1;
  const allowsMoreJobsToSend = isLastSlot ? false : isMidSlot ? true : jobsAllowsMoreJobs;

  const token = localStorage.getItem('auth_token');
  const cid = clusterFilter || clusterId;
  try {
    const res = await fetch(`${API_BASE_URL}/api/allocations/create_allocation/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
      body: JSON.stringify({
        job_activity_id:   act.id ?? act.activity_id,
        mukkadam_id:       mukkadam.mukkadam_id,
        allocated_date:    targetDate,
        allocated_area:    remainingArea,
        allocated_workers: availableWorkers,
        farmer_rate:       act.rate_per_acre ?? 0,
        mukkadam_rate:     Number(rate?.rate_per_acre || 0),
        cluster_id:        cid,
        skip_strict_check: false,
        allows_second_job: allowsMoreJobsToSend,
        job_slot:          slotsUsed + 1,
      }),
    });
    const d = await res.json();
    if (res.ok) {
      const slotLabel = ['1st', '2nd', '3rd'][slotsUsed] ?? `${slotsUsed + 1}th`;
      toast.success(
        allowsMoreJobsToSend
          ? `✅ Allocated to ${mukkadam.mukkadam_name} (⅓ day – ${slotLabel} job)`
          : `✅ Allocated to ${mukkadam.mukkadam_name} (${slotLabel} job – day complete)`,
      );
      setJobsHalfDayDialog(null);
      setJobsAllowsMoreJobs(false);
      setJobsCapacityDate(null); // invalidate cache so next click re-fetches
      fetchDataSilent();
    } else {
      toast.error(d.error || 'Allocation failed');
    }
  } catch {
    toast.error('Allocation failed');
  }
};

const [insightShowDay, setInsightShowDay] = useState<string>('both');
  
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

const [paymentClusterId, setPaymentClusterId] = useState<number | null>(null);


  return (
    <div style={{ minHeight: '100vh', background: '#f0eeeb', fontFamily: S.sans, fontSize: 13, color: S.stone900 }}>
 
      {/* ══════════════════════ TOP BAR ══════════════════════ */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '0 24px', height: 60, background: 'linear-gradient(180deg,#fff 0%,#fdfcfb 100%)', borderBottom: `1px solid ${S.stone200}`, position: 'sticky', top: 0, zIndex: 100, boxShadow: '0 1px 8px rgba(28,25,23,.04)' }}>
 
        {/* Logo */}
        {/* <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingRight: 20, marginRight: 8, borderRight: `1px solid ${S.stone200}` }}>
          <div style={{ width: 34, height: 34, borderRadius: 10, background: 'linear-gradient(135deg,#059669,#065f46)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, boxShadow: '0 2px 8px rgba(5,150,105,.25)' }}>🌿</div>
          <span style={{ fontWeight: 800, fontSize: 17, letterSpacing: '-.3px', color: S.stone800 }}>
            Farm<span style={{ color: S.brand }}>Ops</span>
          </span>
        </div>
        
  */}
  {/* <button onClick={() => navigate('/')}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 10, border: `1px solid ${S.stone200}`, background: '#fff', fontSize: 12, color: S.stone600, cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap' }}>
          ← Back
        </button> */}
        {/* Tab group */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, background: S.stone100, borderRadius: 14, padding: 3, border: `1px solid ${S.stone200}` }}>
          {([
            { key: 'command',   icon: '🏠', label: 'Command',   count: cmdClusters.length },
{ key: 'payment', icon: '💰', label: 'Payment' },
{ key: 'global', icon: '', label: 'Insight' },
            { key: 'mukkadams', icon: '👥', label: 'Mukkadams', count: data?.mukkadams?.length || 0 },
            { key: 'farmers',   icon: '👨‍🌾', label: 'Farmers',   count: data?.farmers?.length   || 0 },
{ key: 'jobs', icon: '📋', label: 'Jobs', count: data?.summary?.total_tender_jobs || 0 },
          ] as const).map(t => {
            const isActive = tab === t.key;
            const isJobs   = t.key === 'jobs';
            return (
              <button key={t.key}
                onClick={() => { setTab(t.key); setNoCluster(false); setClusterFilter(''); if (t.key === 'farmers') setFarmerSubTab('all'); }}
                style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '7px 18px', borderRadius: 11, fontSize: 12, fontWeight: 600, background: isActive ? (isJobs ? S.orange500 : '#fff') : 'transparent', color: isActive ? (isJobs ? '#fff' : S.stone900) : S.stone500, border: 'none', cursor: 'pointer', transition: 'all 250ms', fontFamily: 'inherit', boxShadow: isActive && !isJobs ? '0 1px 3px rgba(28,25,23,.08)' : isActive && isJobs ? '0 2px 8px rgba(249,115,22,.3)' : 'none' }}>
                <span style={{ fontSize: 14 }}>{t.icon}</span>
                {t.label}
                <span style={{ fontSize: 10, fontWeight: 800, padding: '2px 7px', borderRadius: 999, background: isActive ? (isJobs ? 'rgba(255,255,255,.25)' : S.brand) : S.stone200, color: isActive ? '#fff' : S.stone500, boxShadow: isActive && !isJobs ? '0 1px 4px rgba(5,150,105,.3)' : 'none' }}>
                  {t.count}
                </span>
              </button>
            );
          })}
        </div>
 
        {/* Search */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', background: '#fff', border: `1px solid ${S.stone200}`, borderRadius: 14, fontSize: 12, color: S.stone400, maxWidth: 300, flex: 1, transition: 'all 150ms' }}>
          <span>🔍</span>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder={tab === 'mukkadams' ? 'Search mukkadams...' : tab === 'farmers' ? 'Search farmers...' : 'Search...'}
            style={{ border: 'none', outline: 'none', background: 'transparent', flex: 1, fontSize: 12, color: S.stone900, fontFamily: 'inherit' }} />
        </div>
 
        {/* Back */}
        
      </div>
 
      {/* ══════════════════════ STAT CARDS ══════════════════════ */}
      {displaySummary && (
        <div style={{ display: 'flex', gap: 1, background: S.stone200, borderBottom: `1px solid ${S.stone200}` }}>
          {[
            { label: 'Mukkadams',       val: displaySummary.total_mukkadams,   color: '#7c3aed', bg: '#f5f3ff' },
            { label: 'Farmers',         val: displaySummary.total_farmers,     color: S.sky700,  bg: S.sky50   },
            { label: 'Jobs',            val: displaySummary.total_tender_jobs, color: S.stone700, bg: '#fff'   },
            { label: 'Activities',      val: displaySummary.total_activities,  color: S.orange500, bg: '#fff7ed' },
            { label: 'Total Acres',     val: `${Number(displaySummary.total_acres || 0).toFixed(1)} ac`, color: S.green700, bg: S.green50 },
            { label: 'Booking Value',   val: `₹${Number(displaySummary.total_booking_value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#1d4ed8', bg: S.sky50 },
            { label: 'Collected',       val: `₹${Number(displaySummary.total_advance_paid || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: S.green700, bg: S.green50 },
            { label: 'Balance Due',     val: `₹${Number(displaySummary.total_balance || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,    color: S.red700,  bg: S.red50   },
          ].map((s, i) => (
            <div key={i} style={{ flex: 1, padding: '10px 14px', background: s.bg, textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-.5px', lineHeight: 1.2, color: s.color }}>{s.val}</div>
              <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.7px', color: S.stone400, marginTop: 3 }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}
 
      {/* ══════════════════════ FILTER BAR ══════════════════════ */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', padding: '10px 24px', background: 'linear-gradient(180deg,#fdfcfb 0%,#faf9f7 100%)', borderBottom: `1px solid ${S.stone200}` }}>
 
        {/* Farmers sub-pills */}
        {tab === 'farmers' && ([
          { key: 'all',     label: '📁 All',        count: farmerCounts.all     },
          { key: 'new',     label: '🆕 New',         count: farmerCounts.new     },
          { key: 'full',    label: '✅ Clustered',   count: farmerCounts.full    },
          { key: 'partial', label: '⚡ Partial',     count: farmerCounts.partial },
          { key: 'none',    label: '⚠ No Cluster',  count: farmerCounts.none    },
        ] as const).map(t => {
          const active = farmerSubTab === t.key;
          return (
            <button key={t.key} onClick={() => setFarmerSubTab(t.key)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 14px', borderRadius: 999, fontSize: 11, fontWeight: 600, color: active ? '#fff' : S.stone500, background: active ? S.stone800 : '#fff', border: `1px solid ${active ? S.stone800 : S.stone200}`, cursor: 'pointer', transition: 'all 150ms', whiteSpace: 'nowrap', boxShadow: active ? '0 2px 6px rgba(28,25,23,.2)' : '0 1px 2px rgba(0,0,0,.03)', fontFamily: 'inherit' }}>
              {t.label}
              <span style={{ fontWeight: 800, fontSize: 10, padding: '1px 6px', borderRadius: 999, background: active ? 'rgba(255,255,255,.2)' : 'rgba(0,0,0,.06)' }}>{t.count}</span>
            </button>
          );
        })}
 
        {/* Jobs sub-pills */}
        {tab === 'jobs' && ([
          { key: 'all',           label: '📋 All',           count: actCounts.all           },
          { key: 'upcoming',      label: '📅 Next 10 Days',  count: actCounts.upcoming      },
          { key: 'last10',        label: '🕐 Last 10 Days',  count: actCounts.last10        },
          { key: 'split',         label: '🔀 Split',         count: actCounts.split         },
          { key: 'not_allocated', label: '⚠️ Not Allocated', count: actCounts.not_allocated },
          { key: 'in_progress',   label: '⚡ In Progress',   count: actCounts.in_progress   },
          { key: 'completed',     label: '✅ Completed',     count: actCounts.completed     },
        ] as const).map(t => {
          const active = actSubTab === t.key;
          return (
            <button key={t.key} onClick={() => setActSubTab(t.key)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 14px', borderRadius: 999, fontSize: 11, fontWeight: 600, color: active ? '#fff' : S.stone500, background: active ? S.stone800 : '#fff', border: `1px solid ${active ? S.stone800 : S.stone200}`, cursor: 'pointer', transition: 'all 150ms', whiteSpace: 'nowrap', boxShadow: active ? '0 2px 6px rgba(28,25,23,.2)' : '0 1px 2px rgba(0,0,0,.03)', fontFamily: 'inherit' }}>
              {t.label}
              <span style={{ fontWeight: 800, fontSize: 10, padding: '1px 6px', borderRadius: 999, background: active ? 'rgba(255,255,255,.2)' : 'rgba(0,0,0,.06)' }}>{t.count}</span>
            </button>
          );
        })}


        
 
        {/* Mukkadams: no-cluster filter */}
        {tab === 'mukkadams' && (
          <select value={noCluster ? 'NO_CLUSTER' : ''} onChange={e => setNoCluster(e.target.value === 'NO_CLUSTER')}
            style={{ padding: '6px 12px', borderRadius: 10, fontSize: 11, fontWeight: 600, border: `1px solid ${S.stone200}`, background: '#fff', color: S.stone700, cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,.03)', fontFamily: 'inherit' }}>
            <option value="">All Mukkadams</option>
            <option value="NO_CLUSTER">⚠ No Cluster</option>
          </select>
        )}
 
        {/* Right side controls */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
 
          {/* Pruning range — farmers */}
          {tab === 'farmers' && (
            <>
              <span style={{ fontSize: 11, color: S.stone400 }}>🌿</span>
              <input type="date" value={pruningFrom} onChange={e => setPruningFrom(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: 10, border: `1px solid ${S.stone200}`, fontSize: 11, background: '#fff', color: S.stone600, width: 122, fontFamily: 'inherit' }} />
              <span style={{ color: S.stone300, fontSize: 11 }}>–</span>
              <input type="date" value={pruningTo} onChange={e => setPruningTo(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: 10, border: `1px solid ${S.stone200}`, fontSize: 11, background: '#fff', color: S.stone600, width: 122, fontFamily: 'inherit' }} />
              {(pruningFrom || pruningTo) && (
                <button onClick={() => { setPruningFrom(''); setPruningTo(''); }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: S.stone400, fontSize: 12 }}>✕</button>
              )}
            </>
          )}
 
          {/* Cluster filter — farmers */}
          {tab === 'farmers' && (
            <select value={noCluster ? 'NO_CLUSTER' : clusterFilter}
              onChange={e => { if (e.target.value === 'NO_CLUSTER') { setNoCluster(true); setClusterFilter(''); } else { setNoCluster(false); setClusterFilter(e.target.value); } }}
              style={{ padding: '6px 12px', borderRadius: 10, fontSize: 11, fontWeight: 600, border: `1px solid ${S.stone200}`, background: '#fff', color: S.stone700, cursor: 'pointer', fontFamily: 'inherit' }}>
              <option value="">All Clusters</option>
              <option value="NO_CLUSTER">⚠ No Cluster</option>
              {clusters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
 
          {/* Jobs filters */}
          {tab === 'jobs' && (
            <>
              <input placeholder="🔍 Search farmer / activity / plot" value={actSearch} onChange={e => setActSearch(e.target.value)}
                style={{ padding: '6px 12px', borderRadius: 10, border: `1px solid ${S.stone200}`, fontSize: 11, background: '#fff', minWidth: 200, fontFamily: 'inherit', color: S.stone900 }} />
              <select value={actCluster} onChange={e => { setActCluster(e.target.value); setActSubTab('all'); }}
                style={{ padding: '6px 12px', borderRadius: 10, fontSize: 11, fontWeight: 600, border: `1px solid ${S.stone200}`, background: '#fff', color: S.stone700, cursor: 'pointer', fontFamily: 'inherit' }}>
                <option value="">All Clusters</option>
                {clusters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <input type="date" value={actDateFrom} onChange={e => setActDateFrom(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: 10, border: `1px solid ${S.stone200}`, fontSize: 11, background: '#fff', width: 122, fontFamily: 'inherit' }} />
              <span style={{ color: S.stone300, fontSize: 11 }}>–</span>
              <input type="date" value={actDateTo} onChange={e => setActDateTo(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: 10, border: `1px solid ${S.stone200}`, fontSize: 11, background: '#fff', width: 122, fontFamily: 'inherit' }} />
              {(actDateFrom || actDateTo) && (
                <button onClick={() => { setActDateFrom(''); setActDateTo(''); }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: S.stone400, fontSize: 12 }}>✕</button>
              )}
            </>
          )}
        </div>
      </div>
 
      {/* ══════════════════════ CONTENT ══════════════════════ */}
<div style={{ padding: '20px 24px' }}>
  {loading && tab !== 'command' ? (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '80px 0' }}>
      <RefreshCw size={32} style={{ color: S.brand, animation: 'spin 1s linear infinite' }} />
    </div>
) : tab === 'command' ? (
  <>
    {/* ── Search + New Cluster ── */}
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
      <input
        type="text"
        value={cmdSearch}
        onChange={e => setCmdSearch(e.target.value)}
        placeholder="Search clusters..."
        style={{ padding: '8px 14px', borderRadius: 10, border: '1px solid #e8e5de', fontSize: 13, background: '#fff', width: 300, fontFamily: 'inherit', outline: 'none' }}
      />
      <button
        onClick={() => setShowCreateModal(true)}
        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 18px', borderRadius: 12, background: '#16a34a', color: '#fff', fontWeight: 700, fontSize: 13, border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}
      >
        <span style={{ fontSize: 16 }}>+</span> New Cluster
      </button>
    </div>

    {/* ── Alert banner ── */}
    {(() => {
      const critical = cmdClusters.filter(c => c.note);
      if (!critical.length) return null;
      return (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 12, padding: '12px 16px', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span>🔔</span>
            <span style={{ fontWeight: 700, fontSize: 13, color: '#dc2626' }}>
              Action Required — {critical.length} cluster{critical.length > 1 ? 's' : ''} with notes
            </span>
          </div>
          {critical.map(c => (
            <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderTop: '1px solid #fee2e2' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a', minWidth: 160 }}>{c.name}</span>
              <span style={{ fontSize: 12, color: '#6b7280', flex: 1, padding: '0 16px' }}>{c.note}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#dc2626' }}>
                {c.total_area ? `${(Number(c.total_area) - Number(c.allocated_area || 0)).toFixed(1)} ac left` : ''}
              </span>
            </div>
          ))}
        </div>
      );
    })()}

    {/* ── Filter pills ── */}
    {(() => {
      const today = new Date().toISOString().split('T')[0];
      const counts = {
        all:     cmdClusters.length,
        active:  cmdClusters.filter(c => (c.today_team ?? []).length > 0).length,
        blocked: cmdClusters.filter(c => c.note && c.allocated_area === 0).length,
        at_risk: cmdClusters.filter(c => c.note && Number(c.allocated_area) > 0).length,
      };
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
          {[
            { key: 'all',     label: '🗂 All',          count: counts.all     },
            { key: 'active',  label: '✅ Active Today',  count: counts.active  },
            { key: 'blocked', label: '⛔ Blocked',       count: counts.blocked },
            { key: 'at_risk', label: '⚠️ At Risk',       count: counts.at_risk },
          ].map(f => {
            const active = (cmdFilter ?? 'all') === f.key;
            return (
              <button key={f.key} onClick={() => setCmdFilter(f.key)}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 20, border: `1px solid ${active ? '#16a34a' : '#e8e5de'}`, background: active ? '#f0fdf4' : '#fff', color: active ? '#16a34a' : '#7a7a72', cursor: 'pointer', fontSize: 13, fontWeight: 500, fontFamily: 'inherit' }}>
                {f.label}
                <span style={{ background: active ? '#16a34a' : '#e8e5de', color: active ? '#fff' : '#7a7a72', padding: '1px 7px', borderRadius: 10, fontSize: 11, fontWeight: 600 }}>{f.count}</span>
              </button>
            );
          })}
          <div style={{ flex: 1 }} />
          {/* Region filter */}
          <select
            value={cmdRegion ?? 'all'}
            onChange={e => setCmdRegion(e.target.value)}
            style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #e8e5de', background: '#fff', color: '#1a1a1a', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            <option value="all">All Regions</option>
            {[...new Set(cmdClusters.flatMap(c => c.districts ?? []))].map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
      );
    })()}

    {/* ── Cluster cards grid ── */}
    {cmdLoading ? (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '64px 0' }}>
        <RefreshCw size={28} style={{ color: '#16a34a', animation: 'spin 1s linear infinite' }} />
      </div>
    ) : (
      <>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 12, marginBottom: 24 }}>
          {cmdClusters
            .filter(c => {
              const f = cmdFilter ?? 'all';
              if (f === 'active')  return (c.today_team ?? []).length > 0;
              if (f === 'blocked') return c.note && Number(c.allocated_area) === 0;
              if (f === 'at_risk') return c.note && Number(c.allocated_area) > 0;
              return true;
            })
            .filter(c => {
              if (!cmdRegion || cmdRegion === 'all') return true;
              return (c.districts ?? []).includes(cmdRegion);
            })
            .map(c => {
              const totalAc = Number(c.total_area ?? 0);
              const doneAc  = Number(c.allocated_area ?? 0);
              const pct     = totalAc > 0 ? Math.round((doneAc / totalAc) * 100) : 0;
              const remaining = totalAc - doneAc;
              const hasWork = (c.today_team ?? []).length > 0;
              const hasCritical = c.note && Number(c.allocated_area) === 0;
              const hasWarning  = c.note && Number(c.allocated_area) > 0;
              const borderColor = hasCritical ? '#fecaca' : hasWarning ? '#fed7aa' : '#e8e5de';
              const pctColor    = pct > 60 ? '#16a34a' : pct > 25 ? '#f97316' : '#9ca3af';

              return (
                <div key={c.id}
                  style={{ background: '#fff', borderRadius: 12, border: `1px solid ${borderColor}`, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', cursor: 'pointer', transition: 'all 0.15s' }}
                  onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
                  onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.04)'; e.currentTarget.style.transform = 'none'; }}
                >
                  {/* Card header — clickable to open cluster */}
                  <div onClick={() => navigate(`/cluster/${c.id}`)} style={{ padding: '14px 16px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: '#1a1a1a' }}>{c.name}</div>
                      <div style={{ fontSize: 11, color: '#7a7a72', marginTop: 2 }}>
                        {[...(c.districts ?? []), ...(c.talukas ?? [])].slice(0, 2).join(' · ')}
                        {c.date_range?.start_date ? ` · Started ${c.date_range.start_date.slice(5).replace('-', ' ')}` : ''}
                      </div>
                    </div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: pctColor }}>{pct}%</div>
                  </div>

                  {/* Progress bar */}
                  <div style={{ padding: '0 16px 10px' }} onClick={() => navigate(`/cluster/${c.id}`)}>
                    <div style={{ background: '#f0ede7', borderRadius: 5, height: 5, overflow: 'hidden' }}>
                      <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: pctColor, borderRadius: 5, transition: 'width 0.5s ease' }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 5, fontSize: 11, color: '#7a7a72' }}>
                      <span>{doneAc.toFixed(2)} / {totalAc.toFixed(2)} ac</span>
                      <span style={{ fontWeight: 600, color: remaining > 20 ? '#f97316' : '#7a7a72' }}>{remaining.toFixed(1)} ac left</span>
                    </div>
                  </div>

                  {/* Today's assignment */}
                  <div style={{ padding: '10px 16px', margin: '0 10px', background: hasWork ? '#f0fdf4' : '#fafaf8', borderRadius: 8, marginBottom: 10 }}>
                    <div style={{ fontSize: 10, fontWeight: 600, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                      Today — {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long' })}
                    </div>
                    {hasWork ? (
  (() => {
    const seenIds = new Set<string>();
    return (c.today_team ?? []).filter((t: any) => {
      if (seenIds.has(String(t.mukkadam_id))) return false;
      seenIds.add(String(t.mukkadam_id));
      return true;
    }).map((t: any, i: number) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: i > 0 ? 4 : 0 }}>
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: '#16a34a' }}>
                              🧑‍🌾 {t.mukkadam_name} ({t.crew_size})
                            </div>
                            {t.farmer_name && (
                              <div style={{ fontSize: 11, color: '#7a7a72', marginTop: 1 }}>Farmer: {t.farmer_name}</div>
                            )}
                          </div>
                          {t.activity_name && (
                            <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600, background: '#dcfce7', color: '#16a34a' }}>
                              {t.activity_name}
                            </span>
                          )}
                        </div>
                     ))
  })()
) : (
  // No allocation today — show assigned mukkadams from cluster
  // (c.cluster_mukkadams ?? []).length > 0 ? (
  //   (c.cluster_mukkadams as any[]).map((m: any, i: number) => {
  //     const tc = m.mukkadam_type === 'updown'
  //       ? { color: '#ea580c', label: 'Up-Down' }
  //       : { color: '#16a34a', label: 'Permanent' };
  //     return (
  //       <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: i > 0 ? 4 : 0 }}>
  //         <div style={{ fontSize: 12, color: '#6b7280' }}>
  //           🧑‍🌾 <span style={{ fontWeight: 600, color: '#374151' }}>{m.mukkadam_name}</span>
  //           {' '}
  //           <span style={{ color: '#9ca3af' }}>({m.crew_size} crew)</span>
  //         </div>
  //         <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 4, background: m.mukkadam_type === 'updown' ? '#fff7ed' : '#f0fdf4', color: tc.color, border: `1px solid ${m.mukkadam_type === 'updown' ? '#fed7aa' : '#bbf7d0'}` }}>
  //           {tc.label}
  //         </span>
  //       </div>
  //     );
  //   })
  // ) : (
  //   <div style={{ fontSize: 12, color: '#a3a398' }}>🧑‍🌾 No team assigned</div>
  // )
  <></>
)}
                  </div>

                  {/* Alert strip */}
                  {c.note && (
                    <div style={{ padding: '8px 16px', fontSize: 11, lineHeight: 1.4, borderTop: '1px solid #f0ede7', color: hasCritical ? '#ef4444' : '#f97316', background: hasCritical ? '#fef2f2' : '#fff7ed' }}>
                      {hasCritical ? '⛔' : '⚠️'} {c.note}
                    </div>
                  )}

                  {/* Footer: stats + action buttons */}
                  <div style={{ borderTop: '1px solid #f0ede7' }}>
                    {/* Stats row */}
                    <div style={{ display: 'flex', padding: '8px 16px', fontSize: 11, color: '#7a7a72' }}>
                      <span style={{ flex: 1 }}>👥 {c.farmer_count} farmers</span>
                      <span style={{ flex: 1 }}>📋 {c.activity_count} activities</span>
                      <span>{c.mukkadam_count} teams</span>
                    </div>

                    {/* Action buttons */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, padding: '0 10px 10px' }}>
                      <button
                        onClick={e => { e.stopPropagation(); setCmdAddModal({ clusterId: c.id, clusterName: c.name, mode: 'farmer' }); }}
                        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '7px 4px', borderRadius: 10, border: '1px solid #f0ede7', background: '#fafaf8', fontSize: 11, fontWeight: 600, color: '#374151', cursor: 'pointer', fontFamily: 'inherit', gap: 3 }}
                      >
                        <span style={{ width: 28, height: 28, borderRadius: '50%', background: '#ecfdf5', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13 }}>👤</span>
                        Farmer
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); setEditModal(c); }}
                        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '7px 4px', borderRadius: 10, border: '1px solid #f0ede7', background: '#fafaf8', fontSize: 11, fontWeight: 600, color: '#374151', cursor: 'pointer', fontFamily: 'inherit', gap: 3 }}
                      >
                        <span style={{ width: 28, height: 28, borderRadius: '50%', background: '#eef2ff', color: '#4f46e5', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13 }}>✏️</span>
                        Edit
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); setCalendarClusterId(c.id); setCalendarClusterName(c.name); setShowCalendar(true); }}
                        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '7px 4px', borderRadius: 10, border: '1px solid #f0ede7', background: '#fafaf8', fontSize: 11, fontWeight: 600, color: '#374151', cursor: 'pointer', fontFamily: 'inherit', gap: 3 }}
                      >
                        <span style={{ width: 28, height: 28, borderRadius: '50%', background: '#f0f9ff', color: '#0284c7', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13 }}>📅</span>
                        Calendar
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
        </div>

        {/* ── Team Deployment Strip ── */}
        {/* {(() => {
          
          const allMukkadams = new Map<number, any>();
          cmdClusters.forEach(c => {
            (c.cluster_mukkadams ?? []).forEach((m: any) => {
              if (!allMukkadams.has(m.mukkadam_id)) {
                allMukkadams.set(m.mukkadam_id, m);
              }
            });
          });
          const mukkadams = Array.from(allMukkadams.values());
          if (!mukkadams.length) return null;

          const typeColors: Record<string, any> = {
            permanent: { bg: '#f0fdf4', color: '#16a34a', border: '#bbf7d0', label: 'Permanent' },
            updown:    { bg: '#fff7ed', color: '#ea580c', border: '#fed7aa', label: 'Up-Down'   },
          };

          return (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#1a1a1a', marginBottom: 10 }}>
                🧑‍🤝‍🧑 Team Deployment — Today
              </div>
              <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden' }}>
                {mukkadams.map((m, i) => {
                  const tc = typeColors[m.mukkadam_type] ?? typeColors.permanent;
                  const initials = m.mukkadam_name.split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase();
                  return (
                    <div key={m.mukkadam_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', borderBottom: i < mukkadams.length - 1 ? '1px solid #f0ede7' : 'none', fontSize: 13 }}>
                   <div style={{ width: 36, height: 36, borderRadius: '50%', background: tc.bg, border: `1.5px solid ${tc.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: tc.color, flexShrink: 0 }}>
                        {initials}
                      </div>
                    <div style={{ minWidth: 160 }}>
                        <div style={{ fontWeight: 600, color: '#1a1a1a' }}>{m.mukkadam_name}</div>
                        <div style={{ fontSize: 11, color: '#7a7a72' }}>
                          {m.crew_size} crew ·{' '}
                          <span style={{ color: tc.color }}>{tc.label}</span>
                        </div>
                      </div>
                       <div style={{ color: '#7a7a72', fontSize: 18, flexShrink: 0 }}>→</div>
                      <div style={{ flex: 1, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {(m.today_clusters ?? []).length > 0 ? (
  (m.today_clusters as string[]).map((clName, j) => (
    <span key={j} style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: '#f0fdf4', color: '#16a34a', border: '1px solid #bbf7d0' }}>
      🌿 {clName}
    </span>
  ))
) : (
  
  (() => {
    const assignedClusters = cmdClusters.filter(c =>
      (c.cluster_mukkadams ?? []).some((cm: any) => cm.mukkadam_id === m.mukkadam_id)
    );
    return assignedClusters.length > 0 ? (
      assignedClusters.map((c, j) => (
        <span key={j} style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: '#f5f5f4', color: '#78716c', border: '1px solid #e7e5e4' }}>
          📍 {c.name}
        </span>
      ))
    ) : (
      <span style={{ fontSize: 12, color: '#a3a398' }}>No cluster assigned</span>
    );
  })()
)}
                      </div>
                    
                       {m.weekly_amount > 0 && (
                        <div style={{ fontSize: 13, fontWeight: 700, color: '#1a1a1a', flexShrink: 0 }}>
                          ₹{Number(m.weekly_amount).toLocaleString('en-IN')}
                        </div>
                      )} 
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()} */}
      </>
    )}

        {showCalendar && calendarClusterId && (
      <ClusterActivityCalendar
        clusterId={calendarClusterId}
        clusterName={calendarClusterName}
        onClose={() => {
          setShowCalendar(false);
          setCalendarClusterId(null);
          setCalendarClusterName('');
        }}
      />
    )}


    {/* ── Modals ── */}
    {showCreateModal && (
      <CreateClusterModal
        states={states}
        onClose={() => setShowCreateModal(false)}
        onCreate={cluster => {
          setCmdClusters(prev => [...prev, cluster]);
          setShowCreateModal(false);
          navigate(`/cluster/${cluster.id}`);
        }}
      />
    )}
    {editModal && (
      <EditClusterModal
        cluster={editModal}
        onClose={() => setEditModal(null)}
        onSaved={updated => {
          setCmdClusters(prev => prev.map(c => c.id === updated.id ? updated : c));
          setEditModal(null);
        }}
      />
    )}
    {cmdAddModal && (
      <AddToClusterModal
        clusterId={cmdAddModal.clusterId}
        clusterName={cmdAddModal.clusterName}
        mode={cmdAddModal.mode}
        onClose={() => setCmdAddModal(null)}
      />
    )}
  </>

) : tab === 'payment' ? (
  <>
    {/* Sub-tab switcher */}
    <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
      {[
        { key: 'farmer',   label: '🧑‍🌾 Farmer Collections' },
        { key: 'mukkadam', label: '👷 Mukkadam Payouts'    },
      ].map(st => (
        <button key={st.key}
          onClick={() => setPaymentSubTab(st.key as any)}
          style={{ padding: '8px 20px', borderRadius: 20, border: `1.5px solid ${paymentSubTab === st.key ? '#7c3aed' : '#e8e5de'}`, background: paymentSubTab === st.key ? '#f5f3ff' : '#fff', color: paymentSubTab === st.key ? '#7c3aed' : '#6b6b63', fontWeight: paymentSubTab === st.key ? 700 : 500, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          {st.label}
        </button>
      ))}
    </div>

    {paymentSubTab === 'farmer' ? (
  <>
    {paymentLoading || !paymentData ? (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '64px 0' }}>
        <RefreshCw size={28} style={{ color: S.brand, animation: 'spin 1s linear infinite' }} />
      </div>
    ) : (() => {
      const pipe     = paymentData.pipeline ?? {};
      const forecast = paymentData.forecast ?? {};
      const allFarmers: any[] = paymentData.farmer_list ?? [];
      const recentPay: any[]  = paymentData.recent_payments ?? [];
      const clusterBilling: any[] = paymentData.cluster_billing ?? [];

      const fmt = (n: number) => {
        if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
        if (n >= 1000)   return `₹${(n / 1000).toFixed(1)}k`;
        return `₹${n}`;
      };
      const fmtFull = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`;

      // Filtered farmer list
      const filteredFarmers = allFarmers.filter((f: any) => {
        if (paymentFilter === 'ready_to_bill' && f.status !== 'ready_to_bill') return false;
        if (paymentFilter === 'overdue'    && f.expected_payment !== 'overdue')    return false;
        if (paymentFilter === 'this_week'  && f.expected_payment !== 'this_week')  return false;
        if (paymentFilter === 'next_week'  && f.expected_payment !== 'next_week')  return false;
        if (paymentFilter === 'all_billed' && f.status !== 'billed') return false;
        if (paymentClusterFilter  !== 'all' && String(f.cluster_id) !== paymentClusterFilter)  return false;
        if (paymentActivityFilter !== 'all' && f.activity !== paymentActivityFilter) return false;
        return true;
      });

      const uniqueClusters  = [...new Set(allFarmers.map((f: any) => ({id: String(f.cluster_id), name: f.cluster_name})).map(c => JSON.stringify(c)))].map(s => JSON.parse(s));
      const uniqueActivities = [...new Set(allFarmers.map((f: any) => f.activity))];

      const sortedClusters = [...clusterBilling].sort((a: any, b: any) => {
        if (paymentClusterSort === 'due')       return b.due - a.due;
        if (paymentClusterSort === 'collected') return b.collected - a.collected;
        return b.total_job_value - a.total_job_value;
      });

      const totalJobValue  = clusterBilling.reduce((s: number, c: any) => s + (c.total_job_value ?? 0), 0);
      const totalBilled    = clusterBilling.reduce((s: number, c: any) => s + (c.billed ?? 0), 0);
      const totalCollected = clusterBilling.reduce((s: number, c: any) => s + (c.collected ?? 0), 0);
      const totalDue       = clusterBilling.reduce((s: number, c: any) => s + (c.due ?? 0), 0);

      const FILTERS = [
        { key: 'ready_to_bill', label: '📝 Ready to Bill', color: '#ea580c', bg: '#fff7ed', border: '#fed7aa', count: pipe.ready_to_bill?.count ?? 0, amount: pipe.ready_to_bill?.amount ?? 0 },
        { key: 'overdue',       label: '⚠️ Overdue',        color: '#dc2626', bg: '#fef2f2', border: '#fecaca', count: pipe.overdue?.count ?? 0,       amount: pipe.overdue?.amount ?? 0 },
        { key: 'this_week',     label: '📅 This Week',      color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', count: (paymentData.farmer_list ?? []).filter((f:any) => f.expected_payment === 'this_week').length, amount: forecast.this_week?.amount ?? 0 },
        { key: 'next_week',     label: '📆 Next Week',      color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe', count: (paymentData.farmer_list ?? []).filter((f:any) => f.expected_payment === 'next_week').length, amount: forecast.next_week?.amount ?? 0 },
        { key: 'all_billed',    label: '📨 All Billed',     color: '#6b6b63', bg: '#fafaf8', border: '#e8e5de', count: pipe.bills_sent?.count ?? 0,     amount: pipe.bills_sent?.amount ?? 0 },
      ];

      return (
        <>
          {/* ═══ SECTION 1: Pipeline + Forecast ═══ */}
          <div style={{ marginBottom: 28 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
              BILLING PIPELINE & COLLECTION FORECAST
            </div>

            {/* Pipeline cards */}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'stretch', marginBottom: 16 }}>
              {[
                { icon: '📝', label: 'Ready to Bill',   val: pipe.ready_to_bill?.count ?? 0,  amount: pipe.ready_to_bill?.amount ?? 0,  color: '#ea580c', border: '#fed7aa', bg: '#fff7ed', sub: `${pipe.ready_to_bill?.plots ?? 0} plots completed`, onClick: () => setPaymentFilter('ready_to_bill') },
                { icon: '📨', label: 'Bills Sent',       val: pipe.bills_sent?.count ?? 0,     amount: pipe.bills_sent?.amount ?? 0,     color: '#2563eb', border: '#bfdbfe', bg: '#eff6ff', sub: 'Awaiting payment',  onClick: () => setPaymentFilter('all_billed') },
                { icon: '⏰', label: 'Overdue',          val: pipe.overdue?.count ?? 0,        amount: pipe.overdue?.amount ?? 0,        color: '#dc2626', border: '#fecaca', bg: '#fef2f2', sub: pipe.overdue?.count > 0 ? `Avg ${pipe.overdue?.avg_days ?? 0} days late` : 'None', onClick: () => setPaymentFilter('overdue') },
                { icon: '✅', label: 'Collected (30d)',  val: recentPay.length,                amount: pipe.collected_7d?.amount ?? 0,   color: '#16a34a', border: '#bbf7d0', bg: '#f0fdf4', sub: 'Last 30 days', onClick: () => {} },
              ].map((card, i) => (
                <div key={i} style={{ flex: 1, minWidth: 140 }}>
                  {i < 3 && i > 0 && <div style={{ display: 'none' }} />}
                  <div onClick={card.onClick}
                    style={{ background: card.bg, borderRadius: 12, border: `1.5px solid ${card.border}`, padding: '16px 18px', textAlign: 'center', cursor: 'pointer', transition: 'transform 0.1s', height: '100%', boxSizing: 'border-box' as const }}
                    onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-1px)'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.transform = 'none'; }}
                  >
                    <div style={{ fontSize: 13, color: '#6b6b63', fontWeight: 500, marginBottom: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                      <span>{card.icon}</span> {card.label}
                    </div>
                    <div style={{ fontSize: 28, fontWeight: 800, color: card.color, lineHeight: 1.1 }}>{card.val}</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: card.color, marginTop: 4 }}>{fmtFull(card.amount)}</div>
                    {card.sub && <div style={{ fontSize: 11, color: '#a3a398', marginTop: 4 }}>{card.sub}</div>}
                  </div>
                </div>
              ))}
            </div>

            {/* Week-wise forecast bar */}
            <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', padding: '16px 20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>📊</span>
                  <span style={{ fontSize: 13, fontWeight: 700 }}>Collection Forecast</span>
                </div>
                <span style={{ fontSize: 12, color: '#6b6b63' }}>
                  Total outstanding: <strong style={{ color: '#dc2626' }}>{fmtFull((pipe.overdue?.amount ?? 0) + (forecast.this_week?.amount ?? 0) + (forecast.next_week?.amount ?? 0))}</strong>
                </span>
              </div>
              {(() => {
                const total     = (forecast.overdue?.amount ?? 0) + (forecast.this_week?.amount ?? 0) + (forecast.next_week?.amount ?? 0) + (forecast.ready_to_bill?.amount ?? 0);
                const overdueAmt   = forecast.overdue?.amount ?? 0;
                const twAmt        = forecast.this_week?.amount ?? 0;
                const nwAmt        = forecast.next_week?.amount ?? 0;
                const readyAmt     = forecast.ready_to_bill?.amount ?? 0;
                if (total === 0) return <div style={{ textAlign: 'center', color: '#a3a398', fontSize: 13, padding: '16px 0' }}>No outstanding bills</div>;
                return (
                  <>
                    <div style={{ display: 'flex', height: 32, borderRadius: 8, overflow: 'hidden', background: '#f0ede7', marginBottom: 10 }}>
                      {overdueAmt > 0 && <div style={{ width: `${(overdueAmt / total) * 100}%`, background: '#dc2626', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 700, minWidth: 50 }}>{fmt(overdueAmt)}</div>}
                      {twAmt > 0     && <div style={{ width: `${(twAmt / total) * 100}%`,     background: '#16a34a', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 700, minWidth: 50 }}>{fmt(twAmt)}</div>}
                      {nwAmt > 0     && <div style={{ width: `${(nwAmt / total) * 100}%`,     background: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 700, minWidth: 50 }}>{fmt(nwAmt)}</div>}
                      {readyAmt > 0  && <div style={{ width: `${(readyAmt / total) * 100}%`,  background: '#ea580c', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 700, minWidth: 50 }}>{fmt(readyAmt)}</div>}
                    </div>
                    <div style={{ display: 'flex', gap: 20, fontSize: 11, color: '#6b6b63', flexWrap: 'wrap' }}>
                      {[
                        { color: '#dc2626', label: 'Overdue',        amt: overdueAmt },
                        { color: '#16a34a', label: 'This Week',       amt: twAmt },
                        { color: '#2563eb', label: 'Next Week',       amt: nwAmt },
                        { color: '#ea580c', label: 'Ready to Bill',   amt: readyAmt },
                      ].map((item, i) => item.amt > 0 && (
                        <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ width: 8, height: 8, borderRadius: 2, background: item.color, display: 'inline-block' }} />
                          {item.label}: <strong style={{ color: item.color }}>{fmtFull(item.amt)}</strong>
                        </span>
                      ))}
                    </div>
                  </>
                );
              })()}
            </div>
          </div>

          {/* ═══ SECTION 2: Farmer List ═══ */}
          <div style={{ marginBottom: 28 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
              FARMER BILLING LIST
            </div>

            {/* Filter pills */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
              {FILTERS.map(f => {
                const active = paymentFilter === f.key;
                return (
                  <button key={f.key} onClick={() => setPaymentFilter(f.key)}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 20, border: `1px solid ${active ? f.border : '#e8e5de'}`, background: active ? f.bg : '#fff', color: active ? f.color : '#6b6b63', cursor: 'pointer', fontSize: 13, fontWeight: active ? 700 : 500, fontFamily: 'inherit' }}
                  >
                    {f.label}
                    <span style={{ background: active ? f.color : '#e8e5de', color: active ? '#fff' : '#6b6b63', padding: '1px 7px', borderRadius: 10, fontSize: 11, fontWeight: 700 }}>{f.count}</span>
                    {f.amount > 0 && <span style={{ fontSize: 11, color: active ? f.color : '#a3a398' }}>{fmt(f.amount)}</span>}
                  </button>
                );
              })}
            </div>

            {/* Sub-filters */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
              <select value={paymentClusterFilter} onChange={e => setPaymentClusterFilter(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 12, background: '#fff', color: '#1a1a1a', fontFamily: 'inherit' }}>
                <option value="all">All Clusters</option>
                {uniqueClusters.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <select value={paymentActivityFilter} onChange={e => setPaymentActivityFilter(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 12, background: '#fff', color: '#1a1a1a', fontFamily: 'inherit' }}>
                <option value="all">All Activities</option>
                {uniqueActivities.map((a: any) => <option key={a} value={a}>{a}</option>)}
              </select>
              {(paymentClusterFilter !== 'all' || paymentActivityFilter !== 'all') && (
                <button onClick={() => { setPaymentClusterFilter('all'); setPaymentActivityFilter('all'); }}
                  style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626', fontSize: 11, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
                  ✕ Clear
                </button>
              )}
              <span style={{ marginLeft: 'auto', fontSize: 12, color: '#a3a398' }}>{filteredFarmers.length} farmers</span>
            </div>

            {/* Table */}
            <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden' }}>
              {/* Header */}
              <div style={{ display: 'grid', gridTemplateColumns: paymentFilter === 'ready_to_bill' ? 'minmax(180px,2fr) 60px 80px 110px 130px 130px 110px' : 'minmax(180px,2fr) minmax(150px,1.5fr) 90px 80px 110px 110px 110px', padding: '10px 16px', fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.05em', background: '#fafaf8', borderBottom: '1px solid #e8e5de' }}>
                <div>Farmer</div>
                {paymentFilter === 'ready_to_bill' ? (
                  <>
                    <div style={{ textAlign: 'right' }}>Plots</div>
                    <div style={{ textAlign: 'right' }}>Acres</div>
                    <div style={{ textAlign: 'right' }}>Rate</div>
                    <div style={{ textAlign: 'right' }}>Amount</div>
                    <div style={{ textAlign: 'center' }}>Mukkadam</div>
                    <div style={{ textAlign: 'center' }}>Action</div>
                  </>
                ) : (
                  <>
                    <div>Activity</div>
                    <div style={{ textAlign: 'right' }}>Amount</div>
                    <div style={{ textAlign: 'center' }}>Days</div>
                    <div style={{ textAlign: 'center' }}>Status</div>
                    <div style={{ textAlign: 'center' }}>Balance</div>
                    <div style={{ textAlign: 'center' }}>Action</div>
                  </>
                )}
              </div>

              {filteredFarmers.length === 0 ? (
                <div style={{ padding: '40px 16px', textAlign: 'center', color: '#a3a398', fontSize: 13 }}>No records in this view</div>
              ) : filteredFarmers.map((bill: any, i: number) => {
                const key        = `${bill.farmer_id}__${bill.activity}`;
                const isExpanded = expandedFarmerKey === key;
                const isOverdue  = bill.expected_payment === 'overdue';
                const initials   = bill.farmer_name.split(' ').map((w: string) => w[0]).join('').slice(0, 2);

                return (
                  <div key={key} style={{ borderBottom: i < filteredFarmers.length - 1 ? '1px solid #f0ede7' : 'none' }}>
                    {/* Row */}
                    <div
                      onClick={() => handleExpandFarmer(bill)}
                      style={{ display: 'grid', gridTemplateColumns: paymentFilter === 'ready_to_bill' ? 'minmax(180px,2fr) 60px 80px 110px 130px 130px 110px' : 'minmax(180px,2fr) minmax(150px,1.5fr) 90px 80px 110px 110px 110px', padding: '12px 16px', alignItems: 'center', cursor: 'pointer', background: isExpanded ? '#fff8f3' : isOverdue ? 'rgba(254,242,242,0.4)' : 'transparent', transition: 'background 0.15s' }}
                      onMouseEnter={e => { if (!isExpanded) (e.currentTarget as HTMLDivElement).style.background = '#faf9f6'; }}
                      onMouseLeave={e => { if (!isExpanded) (e.currentTarget as HTMLDivElement).style.background = isOverdue ? 'rgba(254,242,242,0.4)' : 'transparent'; }}
                    >
                      {/* Farmer cell */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0, background: isOverdue ? '#fef2f2' : paymentFilter === 'ready_to_bill' ? '#fff7ed' : '#eff6ff', border: `1.5px solid ${isOverdue ? '#fecaca' : paymentFilter === 'ready_to_bill' ? '#fed7aa' : '#bfdbfe'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: isOverdue ? '#dc2626' : paymentFilter === 'ready_to_bill' ? '#ea580c' : '#2563eb' }}>
                          {initials}
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: isExpanded ? '#ea580c' : '#1a1a1a', display: 'flex', alignItems: 'center', gap: 4 }}>
                            {bill.farmer_name}
                            <span style={{ fontSize: 10, color: '#ea580c' }}>{isExpanded ? '▲' : '▼'}</span>
                          </div>
                          <div style={{ fontSize: 11, color: '#a3a398' }}>
                            {bill.cluster_name}{paymentFilter === 'ready_to_bill' ? ` · ${bill.activity}` : ` · ${bill.n_plots} plots · ${bill.acres.toFixed(2)} ac`}
                          </div>
                        </div>
                      </div>

                      {paymentFilter === 'ready_to_bill' ? (
                        <>
                          <div style={{ textAlign: 'right', color: '#6b6b63' }}>{bill.n_plots}</div>
                          <div style={{ textAlign: 'right', fontWeight: 600 }}>{bill.acres.toFixed(2)}</div>
                          <div style={{ textAlign: 'right', color: '#6b6b63' }}>₹{bill.rate.toLocaleString('en-IN')}</div>
                          <div style={{ textAlign: 'right', fontWeight: 700, color: '#ea580c' }}>{fmtFull(bill.amount)}</div>
                          <div style={{ textAlign: 'center', fontSize: 11, color: '#6b6b63' }}>{bill.mukkadam}</div>
                          <div style={{ textAlign: 'center' }}>
                            <span style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: '#fff7ed', color: '#ea580c', border: '1px solid #fed7aa' }}>
                              Generate Bill
                            </span>
                          </div>
                        </>
                      ) : (
                        <>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 500 }}>{bill.activity}</div>
                            <div style={{ fontSize: 11, color: '#a3a398' }}>{bill.mukkadam} · {bill.completed_date?.slice(5).replace('-', ' ')}</div>
                          </div>
                          <div style={{ textAlign: 'right', fontWeight: 700 }}>{fmtFull(bill.amount)}</div>
                          <div style={{ textAlign: 'center' }}>
                            {bill.days_since_billed != null ? (
                              <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, background: isOverdue ? '#fef2f2' : '#f0fdf4', color: isOverdue ? '#dc2626' : '#16a34a' }}>
                                {bill.days_since_billed}d
                              </span>
                            ) : '—'}
                          </div>
                          <div style={{ textAlign: 'center' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, background: isOverdue ? '#fef2f2' : bill.expected_payment === 'this_week' ? '#f0fdf4' : '#eff6ff', color: isOverdue ? '#dc2626' : bill.expected_payment === 'this_week' ? '#16a34a' : '#2563eb' }}>
                              {isOverdue ? '⚠️ Overdue' : bill.expected_payment === 'this_week' ? 'This Week' : 'Next Week'}
                            </span>
                          </div>
                          <div style={{ textAlign: 'right', fontWeight: 700, color: bill.balance_due > 0.01 ? '#dc2626' : '#16a34a' }}>
                            {bill.balance_due > 0.01 ? fmtFull(bill.balance_due) : '✓ Clear'}
                          </div>
                          <div style={{ textAlign: 'center', fontSize: 11, color: '#a3a398' }}>
                            {bill.billed_date?.slice(5).replace('-', ' ')}
                          </div>
                        </>
                      )}
                    </div>

                    {/* Expanded farmer detail */}
                    {isExpanded && (
                      <div style={{ background: '#fffcfa', borderTop: '1px solid #fed7aa' }}>
                        {expandedFarmerLoading ? (
                          <div style={{ padding: '24px', textAlign: 'center', color: '#a3a398' }}>Loading farmer detail...</div>
                        ) : expandedFarmerData ? (
                          <div style={{ padding: '16px 20px' }}>
                            {/* Header */}
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f0ede7', marginBottom: 12 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span>📋</span>
                                <span style={{ fontSize: 13, fontWeight: 700, color: '#ea580c' }}>Billing Detail — {expandedFarmerData.farmer_name}</span>
                                <span style={{ fontSize: 11, color: '#6b6b63' }}>{bill.cluster_name} · {expandedFarmerData.total_plots ?? 0} plots</span>
                              </div>
                              <button onClick={() => { setExpandedFarmerKey(null); setExpandedFarmerData(null); }}
                                style={{ padding: '4px 12px', borderRadius: 8, border: '1px solid #fed7aa', background: '#fff', cursor: 'pointer', fontSize: 11, color: '#ea580c', fontWeight: 600, fontFamily: 'inherit' }}>
                                ▲ Collapse
                              </button>
                            </div>

                            {/* Summary bar */}
                            <div style={{ display: 'flex', borderRadius: 10, overflow: 'hidden', border: '1px solid #e8e5de', marginBottom: 16 }}>
                              {[
                                { label: 'Total Job Value', val: fmtFull(expandedFarmerData.jobs?.reduce((s: number, j: any) => s + (j.total_job_amount ?? 0), 0) ?? 0), color: '#1a1a1a' },
                                { label: 'Total Billed',    val: fmtFull(expandedFarmerData.jobs?.reduce((s: number, j: any) => s + (j.summary?.total_billable_so_far ?? 0), 0) ?? 0), color: '#2563eb' },
                                { label: 'Total Collected', val: fmtFull(expandedFarmerData.jobs?.reduce((s: number, j: any) => s + (j.summary?.total_paid ?? 0), 0) ?? 0), color: '#16a34a' },
                                { label: 'Balance Due',     val: (() => { const due = expandedFarmerData.jobs?.reduce((s: number, j: any) => s + (j.summary?.balance_due ?? 0), 0) ?? 0; return due > 0.01 ? fmtFull(due) : '✓ Clear'; })(), color: (() => { const due = expandedFarmerData.jobs?.reduce((s: number, j: any) => s + (j.summary?.balance_due ?? 0), 0) ?? 0; return due > 0.01 ? '#dc2626' : '#16a34a'; })() },
                              ].map((item, idx) => (
                                <div key={idx} style={{ flex: 1, padding: '12px 16px', borderLeft: idx > 0 ? '1px solid #e8e5de' : 'none' }}>
                                  <div style={{ fontSize: 10, fontWeight: 600, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>{item.label}</div>
                                  <div style={{ fontSize: 18, fontWeight: 800, color: item.color }}>{item.val}</div>
                                </div>
                              ))}
                            </div>

                            {/* Activity cards — reuse FarmerBillingPage logic inline */}
                            <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
                              ACTIVITIES · BILLING STATUS
                            </div>
                            {/* Render the same FarmerBillingPage embedded */}
                            <div style={{ height: 500, overflow: 'hidden', margin: '0 -20px', borderTop: '1px solid #f0ede7' }}>
                              <FarmerBillingPage clusterId={bill.cluster_id} embeddedFarmerId={String(bill.farmer_id)} />
                            </div>
                          </div>
                        ) : (
                          <div style={{ padding: '24px', textAlign: 'center', color: '#a3a398' }}>No detail available</div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* ═══ SECTION 3: Cluster Billing Summary ═══ */}
          <div style={{ marginBottom: 28 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.06em' }}>CLUSTER BILLING SUMMARY</span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                {[
                  { key: 'due',       label: 'Sort: Due'       },
                  { key: 'collected', label: 'Sort: Collected' },
                  { key: 'value',     label: 'Sort: Job Value' },
                ].map(s => (
                  <button key={s.key} onClick={() => setPaymentClusterSort(s.key)}
                    style={{ padding: '4px 10px', borderRadius: 6, border: `1px solid ${paymentClusterSort === s.key ? '#e8e5de' : '#e8e5de'}`, background: paymentClusterSort === s.key ? '#1a1a1a' : '#fff', color: paymentClusterSort === s.key ? '#fff' : '#6b6b63', fontSize: 11, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'auto' }}>
              {/* Header */}
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(140px,2fr) 60px 100px 100px 100px 100px 80px 80px 80px', padding: '10px 16px', fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.05em', background: '#fafaf8', borderBottom: '1px solid #e8e5de', minWidth: 860 }}>
                <div>Cluster</div>
                <div style={{ textAlign: 'right' }}>Farmers</div>
                <div style={{ textAlign: 'right' }}>Job Value</div>
                <div style={{ textAlign: 'right' }}>Billed</div>
                <div style={{ textAlign: 'right' }}>Collected</div>
                <div style={{ textAlign: 'right' }}>Due</div>
                <div style={{ textAlign: 'center' }}>Pending</div>
                <div style={{ textAlign: 'center' }}>Sent</div>
                <div style={{ textAlign: 'center' }}>Await</div>
              </div>
              {sortedClusters.map((c: any, i: number) => (
                <div key={c.cluster_id}
                  onClick={() => setPaymentClusterId(c.cluster_id)}
                  style={{ display: 'grid', gridTemplateColumns: 'minmax(140px,2fr) 60px 100px 100px 100px 100px 80px 80px 80px', padding: '10px 16px', fontSize: 13, alignItems: 'center', borderBottom: i < sortedClusters.length - 1 ? '1px solid #f0ede7' : 'none', minWidth: 860, cursor: 'pointer', transition: 'background 0.1s' }}
                  onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = '#fafaf8'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                >
                  <div style={{ fontWeight: 600 }}>{c.cluster}</div>
                  <div style={{ textAlign: 'right', color: '#6b6b63' }}>{c.farmers}</div>
                  <div style={{ textAlign: 'right', color: '#6b6b63' }}>{fmt(c.total_job_value)}</div>
                  <div style={{ textAlign: 'right', fontWeight: 600, color: c.billed > 0 ? '#2563eb' : '#a3a398' }}>{fmt(c.billed)}</div>
                  <div style={{ textAlign: 'right', fontWeight: 600, color: c.collected > 0 ? '#16a34a' : '#a3a398' }}>{fmt(c.collected)}</div>
                  <div style={{ textAlign: 'right', fontWeight: 700, color: c.due > 0 ? '#dc2626' : '#16a34a' }}>{c.due > 0 ? fmt(c.due) : '✓'}</div>
                  <div style={{ textAlign: 'center' }}>
                    {c.bills_pending > 0 ? <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 700, background: '#fff7ed', color: '#ea580c' }}>{c.bills_pending}</span> : <span style={{ color: '#a3a398' }}>0</span>}
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    {c.bills_sent > 0 ? <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 700, background: '#eff6ff', color: '#2563eb' }}>{c.bills_sent}</span> : <span style={{ color: '#a3a398' }}>0</span>}
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    {c.bills_awaiting > 0 ? <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 700, background: '#fef2f2', color: '#dc2626' }}>{c.bills_awaiting}</span> : <span style={{ color: '#a3a398' }}>0</span>}
                  </div>
                </div>
              ))}
              {/* Totals row */}
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(140px,2fr) 60px 100px 100px 100px 100px 80px 80px 80px', padding: '10px 16px', fontSize: 13, fontWeight: 700, background: '#f5f4ef', borderTop: '2px solid #e8e5de', minWidth: 860 }}>
                <div>Total</div>
                <div style={{ textAlign: 'right' }}>{clusterBilling.reduce((s: number, c: any) => s + (c.farmers ?? 0), 0)}</div>
                <div style={{ textAlign: 'right' }}>{fmt(totalJobValue)}</div>
                <div style={{ textAlign: 'right', color: '#2563eb' }}>{fmt(totalBilled)}</div>
                <div style={{ textAlign: 'right', color: '#16a34a' }}>{fmt(totalCollected)}</div>
                <div style={{ textAlign: 'right', color: '#dc2626' }}>{fmt(totalDue)}</div>
                <div style={{ textAlign: 'center', color: '#ea580c' }}>{clusterBilling.reduce((s: number, c: any) => s + (c.bills_pending ?? 0), 0)}</div>
                <div style={{ textAlign: 'center', color: '#2563eb' }}>{clusterBilling.reduce((s: number, c: any) => s + (c.bills_sent ?? 0), 0)}</div>
                <div style={{ textAlign: 'center', color: '#dc2626' }}>{clusterBilling.reduce((s: number, c: any) => s + (c.bills_awaiting ?? 0), 0)}</div>
              </div>
            </div>
          </div>

          {/* ═══ SECTION 4: Recent Payments ═══ */}
          <div style={{ marginBottom: 28 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <span>✅</span>
              <span style={{ fontSize: 13, fontWeight: 700 }}>Recent Payments</span>
              <span style={{ fontSize: 12, color: '#6b6b63' }}>Last 30 days</span>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {recentPay.map((p: any, i: number) => (
                <div key={i} style={{ background: '#fff', borderRadius: 10, padding: '12px 16px', border: '1px solid #bbf7d0', minWidth: 200, flex: '1 1 200px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{p.farmer}</div>
                      <div style={{ fontSize: 11, color: '#a3a398' }}>{p.cluster}</div>
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#16a34a' }}>{fmtFull(p.amount)}</div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: '#6b6b63' }}>
                    <span>{p.paid_date?.slice(5).replace('-', ' ')}</span>
                    <span style={{ padding: '1px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600, background: p.method === 'UPI' ? '#ede9fe' : p.method === 'CASH' ? '#fefce8' : '#eff6ff', color: p.method === 'UPI' ? '#7c3aed' : p.method === 'CASH' ? '#ca8a04' : '#2563eb' }}>
                      {p.method}
                    </span>
                  </div>
                  {p.notes && <div style={{ fontSize: 10, color: '#a3a398', marginTop: 4 }}>{p.notes}</div>}
                </div>
              ))}
            </div>
          </div>
        </>
      );
    })()}
  </> ) : (
<>

        <MukkadamPayout/>
      </>
    )}
  </>)

: tab === 'global' ? (
  <>
    {insightsLoading || !insightsData ? (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '64px 0' }}>
        <RefreshCw size={28} style={{ color: S.brand, animation: 'spin 1s linear infinite' }} />
      </div>
    ) : (() => {
      const kpi    = insightsData.global_kpis;
      const days   = insightsData.days ?? [];
      const daily  = insightsData.global_daily ?? [];
      const raw    = insightsData.clusters ?? [];

      const sorted = [...raw].sort((a: any, b: any) => {
        if (insightSort === 'pending')  return b.pending_area - a.pending_area;
        if (insightSort === 'progress') return a.pct - b.pct;
        if (insightSort === 'name')     return a.name.localeCompare(b.name);
        return 0;
      });
   
      const redCount   = raw.filter((c: any) => c.today?.status === 'red'   || c.tomorrow?.status === 'red').length;
      const greenCount = raw.filter((c: any) => c.today?.status === 'green' && c.tomorrow?.status === 'green').length;

      const statusDot = (status: string) => {
        const colors: Record<string,string> = { green: '#16a34a', red: '#dc2626', yellow: '#ca8a04' };
        const bgs:    Record<string,string> = { green: '#f0fdf4', red: '#fef2f2', yellow: '#fefce8' };
        return <span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: '50%', background: colors[status] || '#aaa', flexShrink: 0, boxShadow: `0 0 0 3px ${bgs[status] || '#f5f5f5'}` }} />;
      };

      const typeTagStyle = (tag: string) => ({
        fontSize: 9, fontWeight: 800 as const, padding: '1px 5px', borderRadius: 4,
        background: tag === 'UP' ? '#fff7ed' : '#f0fdf4',
        color:      tag === 'UP' ? '#ea580c' : '#16a34a',
        border:     `1px solid ${tag === 'UP' ? '#fed7aa' : '#bbf7d0'}`,
        marginLeft: 3, lineHeight: '14px' as const,
      });

      const pctColor = (pct: number) => pct > 60 ? '#16a34a' : pct > 25 ? '#ea580c' : '#dc2626';

      return (
        <>
          {/* ═══ SECTION 1: Global KPIs ═══ */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: S.stone700, marginBottom: 12 }}>🌍 Overall Progress</div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
              {[
                { label: 'Farmers',    val: kpi.total_farmers,                          color: '#16a34a' },
                { label: 'Plots',      val: kpi.total_plots,                            color: S.stone700 },
                { label: 'Total Acres', val: `${Number(kpi.total_area).toFixed(1)} ac`, color: S.stone700 },
                { label: 'Allocated',  val: `${Number(kpi.allocated_area).toFixed(1)} ac`, color: '#2563eb' },
                { label: 'Pending',    val: `${Number(kpi.pending_area).toFixed(1)} ac`, color: '#dc2626' },
                { label: '% Done',     val: `${kpi.pct_complete}%`,                     color: '#16a34a' },
                { label: 'Jobs',       val: kpi.total_jobs,                              color: '#ea580c' },
                { label: 'Activities', val: kpi.total_activities,                        color: S.stone700 },
              ].map((k, i) => (
                <div key={i} style={{ background: '#fff', borderRadius: 12, padding: '14px 18px', border: '1px solid #e8e5de', flex: 1, minWidth: 100, textAlign: 'center' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: k.color, lineHeight: 1.1 }}>{k.val}</div>
                  <div style={{ fontSize: 10, color: '#6b6b63', fontWeight: 600, marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{k.label}</div>
                </div>
              ))}
            </div>
            <div style={{ background: '#fff', borderRadius: 10, padding: '10px 16px', border: '1px solid #e8e5de' }}>
              <div style={{ background: '#f0ede7', borderRadius: 5, height: 8, overflow: 'hidden', marginBottom: 6 }}>
                <div style={{ width: `${Math.min(kpi.pct_complete, 100)}%`, height: '100%', borderRadius: 5, background: pctColor(kpi.pct_complete), transition: 'width 0.4s ease' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#6b6b63' }}>
                <span>{Number(kpi.allocated_area).toFixed(1)} ac allocated</span>
                <span>{Number(kpi.pending_area).toFixed(1)} ac remaining</span>
              </div>
            </div>
          </div>

          {/* ═══ SECTION 2: Cluster Breakdown Table ═══ */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: S.stone700, marginBottom: 12 }}>
              📋 Cluster Breakdown
              <span style={{ marginLeft: 8, padding: '2px 9px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: '#f0fdf4', color: '#16a34a', border: '1px solid #bbf7d0' }}>{raw.length}</span>
            </div>
            <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden' }}>
              {/* Header */}
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(160px, 2fr) 70px 70px 90px 60px 90px 90px 100px', padding: '10px 16px', fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.05em', background: '#fafaf8', borderBottom: '1px solid #e8e5de' }}>
                <div>Cluster</div>
                <div style={{ textAlign: 'right' }}>Farmers</div>
                <div style={{ textAlign: 'right' }}>Plots</div>
                <div style={{ textAlign: 'right', cursor: 'pointer', color: insightSort === 'pending' ? '#16a34a' : '#a3a398' }} onClick={() => setInsightSort('pending')}>Total Ac ↕</div>
                <div style={{ textAlign: 'right' }}>Jobs</div>
                <div style={{ textAlign: 'right' }}>Allocated</div>
                <div style={{ textAlign: 'right', cursor: 'pointer', color: insightSort === 'pending' ? '#16a34a' : '#a3a398' }} onClick={() => setInsightSort('pending')}>Pending ↕</div>
                <div style={{ textAlign: 'center', cursor: 'pointer', color: insightSort === 'progress' ? '#16a34a' : '#a3a398' }} onClick={() => setInsightSort('progress')}>Progress ↕</div>
              </div>

              {/* Rows */}
              {/* Rows */}
{sorted.map((cluster: any, i: number) => {
  const pct = cluster.pct ?? 0;
  const pc  = pctColor(pct);
  const isExpanded = expandedCluster === cluster.id;
  return (
    <React.Fragment key={cluster.id}>
      {/* ── Main row ── */}
      <div
        style={{ display: 'grid', gridTemplateColumns: 'minmax(160px, 2fr) 70px 70px 90px 60px 90px 90px 100px', padding: '10px 16px', fontSize: 13, borderBottom: isExpanded ? 'none' : (i < sorted.length - 1 ? '1px solid #f0ede7' : 'none'), alignItems: 'center', background: insightHover === cluster.id ? '#fafaf8' : 'transparent', transition: 'background 0.1s', cursor: 'pointer' }}
        onMouseEnter={() => setInsightHover(cluster.id)}
        onMouseLeave={() => setInsightHover(null)}
        onClick={() => setExpandedCluster(isExpanded ? null : cluster.id)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          {statusDot(cluster.today?.status)}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
              {cluster.name}
              <span style={{ fontSize: 8, color: '#a3a398', display: 'inline-block', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>▼</span>
            </div>
            {cluster.note && <div style={{ fontSize: 10, color: '#ea580c', marginTop: 1 }}>{cluster.note.slice(0, 50)}{cluster.note.length > 50 ? '…' : ''}</div>}
          </div>
        </div>
        <div style={{ textAlign: 'right', color: '#6b6b63' }}>{cluster.farmers}</div>
        <div style={{ textAlign: 'right', color: '#6b6b63' }}>{cluster.plots}</div>
        <div style={{ textAlign: 'right', fontWeight: 600 }}>{Number(cluster.total_area).toFixed(1)}</div>
        <div style={{ textAlign: 'right', color: '#6b6b63' }}>{cluster.jobs}</div>
        <div style={{ textAlign: 'right', color: '#16a34a', fontWeight: 600 }}>{Number(cluster.allocated_area).toFixed(1)}</div>
        <div style={{ textAlign: 'right', color: Number(cluster.pending_area) > 20 ? '#dc2626' : Number(cluster.pending_area) > 0 ? '#ea580c' : '#16a34a', fontWeight: 700 }}>{Number(cluster.pending_area).toFixed(1)}</div>
        <div style={{ paddingLeft: 8 }}>
          <div style={{ background: '#f0ede7', borderRadius: 4, height: 5, overflow: 'hidden' }}>
            <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: pc, borderRadius: 4 }} />
          </div>
          <div style={{ fontSize: 10, textAlign: 'center', color: '#a3a398', marginTop: 2 }}>{pct.toFixed(0)}%</div>
        </div>

        {/* ── 7-day area strip (always visible) ── */}

      </div>

      {/* ── Expandable activity breakdown ── */}
      {isExpanded && (
        <div style={{ padding: '10px 16px 12px 48px', background: '#f8fdf9', borderBottom: i < sorted.length - 1 ? '1px solid #f0ede7' : 'none', borderTop: '1px dashed #d1fae5' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#16a34a', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Pending by Activity
          </div>
          {cluster.activity_breakdown?.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 10px' }}>
              {cluster.activity_breakdown.map((ab: any) => (
                <div key={ab.activity} style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#fff', border: '1px solid #e8e5de', borderRadius: 8, padding: '4px 10px' }}>
                  <span style={{ fontSize: 11, color: '#374151', fontWeight: 600 }}>{ab.activity}</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: ab.pending_area > 20 ? '#dc2626' : ab.pending_area > 0 ? '#ea580c' : '#16a34a' }}>
                    {ab.pending_area.toFixed(1)} ac
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 12, color: '#16a34a', fontWeight: 600 }}>✓ All activities allocated</div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6, padding: '8px 16px 10px 16px', background: '#fafaf9', borderTop: '1px solid #f0ede7', borderBottom: isExpanded ? 'none' : (i < sorted.length - 1 ? '1px solid #f0ede7' : 'none') }}>
  {(cluster.week_plan ?? []).map((day: any) => {
    const hasData = day.total_area > 0;
    const pendingColor = day.pending_area > 20 ? '#dc2626' : day.pending_area > 0 ? '#ea580c' : '#16a34a';
    return (
      <div key={day.date} style={{ background: day.is_today ? '#f0fdf4' : '#fff', border: `1px solid ${day.is_today ? '#bbf7d0' : '#e8e5de'}`, borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
        {/* Day name */}
        <div style={{ fontSize: 9, fontWeight: 700, color: day.is_today ? '#16a34a' : '#a3a398', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
          {day.day_name}
        </div>
        {hasData ? (
          <>
            {/* Total */}
            <div style={{ fontSize: 10, color: '#6b6b63', marginBottom: 1 }}>
              <span style={{ fontWeight: 600, color: '#374151' }}>{day.total_area.toFixed(1)}</span>
              <span style={{ fontSize: 8, color: '#a3a398' }}> ac</span>
            </div>
            {/* Allocated */}
            <div style={{ fontSize: 10, color: '#16a34a', marginBottom: 1 }}>
              ✓ {day.allocated_area.toFixed(1)}
            </div>
            {/* Pending */}
            <div style={{ fontSize: 10, fontWeight: 700, color: pendingColor }}>
              ⏳ {day.pending_area.toFixed(1)}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 9, color: '#d1d5db', marginTop: 4 }}>—</div>
        )}
      </div>
    );
  })}
</div>

        </div>
      )}
    </React.Fragment>
  );
})}
              {/* Totals row */}
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(160px, 2fr) 70px 70px 90px 60px 90px 90px 100px', padding: '10px 16px', fontSize: 13, fontWeight: 700, background: '#f5f4ef', borderTop: '2px solid #e8e5de' }}>
                <div>Total</div>
                <div style={{ textAlign: 'right' }}>{raw.reduce((s: number, c: any) => s + (c.farmers ?? 0), 0)}</div>
                <div style={{ textAlign: 'right' }}>{raw.reduce((s: number, c: any) => s + (c.plots ?? 0), 0)}</div>
                <div style={{ textAlign: 'right' }}>{raw.reduce((s: number, c: any) => s + Number(c.total_area ?? 0), 0).toFixed(1)}</div>
                <div style={{ textAlign: 'right' }}>{raw.reduce((s: number, c: any) => s + (c.jobs ?? 0), 0)}</div>
                <div style={{ textAlign: 'right', color: '#16a34a' }}>{raw.reduce((s: number, c: any) => s + Number(c.allocated_area ?? 0), 0).toFixed(1)}</div>
                <div style={{ textAlign: 'right', color: '#dc2626' }}>{raw.reduce((s: number, c: any) => s + Number(c.pending_area ?? 0), 0).toFixed(1)}</div>
                <div style={{ paddingLeft: 8 }}>
                  <div style={{ background: '#f0ede7', borderRadius: 4, height: 5, overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(kpi.pct_complete, 100)}%`, height: '100%', background: pctColor(kpi.pct_complete), borderRadius: 4 }} />
                  </div>
                  <div style={{ fontSize: 10, textAlign: 'center', color: '#a3a398', marginTop: 2 }}>{kpi.pct_complete}%</div>
                </div>
              </div>

              {/* No Cluster row */}
{insightsData.no_cluster_row && (() => {
  const nc = insightsData.no_cluster_row;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(160px, 2fr) 70px 70px 90px 60px 90px 90px 100px', padding: '10px 16px', fontSize: 13, background: '#fefce8', borderTop: '1px solid #fde68a', alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <span style={{ fontSize: 11 }}>⚠️</span>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#ca8a04' }}>{nc.name}</div>
      </div>
      <div style={{ textAlign: 'right', color: '#6b6b63' }}>{nc.farmers}</div>
      <div style={{ textAlign: 'right', color: '#6b6b63' }}>{nc.plots}</div>
      <div style={{ textAlign: 'right', fontWeight: 600 }}>{Number(nc.total_area).toFixed(1)}</div>
      <div style={{ textAlign: 'right', color: '#6b6b63' }}>{nc.jobs}</div>
      <div style={{ textAlign: 'right', color: '#16a34a', fontWeight: 600 }}>{Number(nc.allocated_area).toFixed(1)}</div>
      <div style={{ textAlign: 'right', color: '#ca8a04', fontWeight: 700 }}>{Number(nc.pending_area).toFixed(1)}</div>
      <div style={{ paddingLeft: 8 }}>
        <div style={{ background: '#f0ede7', borderRadius: 4, height: 5, overflow: 'hidden' }}>
          <div style={{ width: `${Math.min(nc.pct, 100)}%`, height: '100%', background: '#ca8a04', borderRadius: 4 }} />
        </div>
        <div style={{ fontSize: 10, textAlign: 'center', color: '#a3a398', marginTop: 2 }}>{nc.pct}%</div>
      </div>
    </div>
  );
})()}
            </div>
          </div>

          {/* ═══ SECTION 3: Today & Tomorrow Traffic Lights ═══ */}
          {(() => {
            const [showDay, setShowDay] = [insightShowDay, setInsightShowDay];
            return (
              <div style={{ marginBottom: 24 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: S.stone700, marginBottom: 12 }}>🚦 Today & Tomorrow — What Needs Attention</div>
                {/* Filter pills */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center' }}>
                  {[
                    { key: 'both',     label: 'Both Days'           },
                    { key: 'today',    label: `Today (${(insightsData.today ?? '').slice(5).replace('-', ' ')})`    },
                    { key: 'tomorrow', label: `Tomorrow (${(insightsData.tomorrow ?? '').slice(5).replace('-', ' ')})` },
                  ].map(f => (
                    <button key={f.key} onClick={() => setInsightShowDay(f.key)}
                      style={{ padding: '5px 14px', borderRadius: 20, cursor: 'pointer', border: `1px solid ${insightShowDay === f.key ? '#16a34a' : '#e8e5de'}`, background: insightShowDay === f.key ? '#f0fdf4' : '#fff', color: insightShowDay === f.key ? '#16a34a' : '#6b6b63', fontSize: 12, fontWeight: 600, fontFamily: 'inherit' }}
                    >{f.label}</button>
                  ))}
                  <div style={{ flex: 1 }} />
                  <span style={{ fontSize: 12, color: '#6b6b63', display: 'flex', alignItems: 'center', gap: 4 }}>
                    {statusDot('red')} {redCount} need action
                  </span>
                  <span style={{ fontSize: 12, color: '#6b6b63', display: 'flex', alignItems: 'center', gap: 4, marginLeft: 10 }}>
                    {statusDot('green')} {greenCount} all clear
                  </span>
                </div>

                {/* Cards grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                  {raw.map((cluster: any) => {
                    const tod  = cluster.today    ?? { status: 'red', msg: '—' };
                    const tmrw = cluster.tomorrow ?? { status: 'red', msg: '—' };
                    const worst = tod.status === 'red' || tmrw.status === 'red' ? 'red'
                      : tod.status === 'yellow' || tmrw.status === 'yellow' ? 'yellow' : 'green';
                    const borderColor = worst === 'red' ? '#fecaca' : worst === 'yellow' ? '#fde68a' : '#bbf7d0';
                    const bgColor     = worst === 'red' ? '#fef2f2' : worst === 'yellow' ? '#fefce8' : '#f0fdf4';
                    const textColor   = (s: string) => s === 'green' ? '#6b6b63' : s === 'red' ? '#dc2626' : '#ca8a04';

                    return (
                      <div key={cluster.id} style={{ background: '#fff', borderRadius: 10, border: `1.5px solid ${borderColor}`, overflow: 'hidden', transition: 'transform 0.1s' }}
                        onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-1px)'; }}
                        onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.transform = 'none'; }}
                      >
                        {/* Card header */}
                        <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8, background: bgColor, borderBottom: `1px solid ${borderColor}` }}>
                          {statusDot(worst)}
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 13, fontWeight: 700 }}>{cluster.name}</div>
                            <div style={{ fontSize: 10, color: '#6b6b63' }}>
                              {(cluster.districts ?? []).slice(0,1).join('')} · {Number(cluster.pending_area).toFixed(1)} ac pending
                            </div>
                          </div>
                        </div>

                        {/* Today row */}
                        {(insightShowDay === 'both' || insightShowDay === 'today') && (
                          <div style={{ padding: '8px 14px', display: 'flex', alignItems: 'flex-start', gap: 8, borderBottom: insightShowDay === 'both' ? '1px solid #f0ede7' : 'none' }}>
                            <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', minWidth: 46, textTransform: 'uppercase', paddingTop: 2 }}>Today</div>
                            {statusDot(tod.status)}
                            <div style={{ fontSize: 12, color: textColor(tod.status), lineHeight: 1.4 }}>{tod.msg}</div>
                          </div>
                        )}

                        {/* Tomorrow row */}
                        {(insightShowDay === 'both' || insightShowDay === 'tomorrow') && (
                          <div style={{ padding: '8px 14px', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                            <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', minWidth: 46, textTransform: 'uppercase', paddingTop: 2 }}>Tmrw</div>
                            {statusDot(tmrw.status)}
                            <div style={{ fontSize: 12, color: textColor(tmrw.status), lineHeight: 1.4 }}>{tmrw.msg}</div>
                          </div>
                        )}

                        {/* No cluster card */}

                      </div>

                      
                    );
                  })}
                </div>

                
              </div>
            );
          })()}

          {/* ═══ SECTION 4: 7-Day Plan Grid ═══ */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: S.stone700, marginBottom: 12 }}>📅 Next 7 Days — Team Availability</div>

            {/* Legend */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: 12, color: '#6b6b63', marginRight: 4 }}>Legend:</span>
              <span style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 500, border: '1px solid #e8e5de', background: '#f5f5f0', color: '#1a1a1a' }}>
                Name <span style={{ background: '#e8e5de', padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 700, color: '#6b6b63', marginLeft: 2 }}>12</span>
              </span>
              <span style={{ padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 800, background: '#fff7ed', color: '#ea580c', border: '1px solid #fed7aa' }}>UP</span>
              <span style={{ fontSize: 11, color: '#6b6b63' }}>= Up-Down</span>
              <span style={{ padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 800, background: '#f0fdf4', color: '#16a34a', border: '1px solid #bbf7d0' }}>P</span>
              <span style={{ fontSize: 11, color: '#6b6b63' }}>= Permanent</span>
              <span style={{ fontSize: 11, color: '#dc2626', background: '#fef2f2', padding: '3px 8px', borderRadius: 4, border: '1px solid #fecaca' }}>N unalloc</span>
              <span style={{ fontSize: 11, color: '#6b6b63' }}>= unallocated jobs</span>
            </div>

            <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'auto' }}>
              {/* Day headers */}
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(150px, 180px) repeat(7, 1fr)', borderBottom: '2px solid #e8e5de' }}>
                <div style={{ padding: '10px 14px', fontSize: 11, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', background: '#fafaf8', borderRight: '1px solid #e8e5de' }}>Cluster</div>
                {days.map((d: any, i: number) => (
                  <div key={i} style={{ padding: '8px 6px', textAlign: 'center', background: i === 0 ? '#f0fdf4' : '#fafaf8', borderRight: i < 6 ? '1px solid #f0ede7' : 'none', borderBottom: i === 0 ? '2px solid #16a34a' : 'none' }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: i === 0 ? '#16a34a' : '#1a1a1a' }}>{d.label}</div>
                    <div style={{ fontSize: 10, color: '#a3a398' }}>{d.day_name}</div>
                  </div>
                ))}
              </div>

              {/* Cluster rows */}
              {sorted.map((cluster: any) => (
                <div key={cluster.id}
                  style={{ display: 'grid', gridTemplateColumns: 'minmax(150px, 180px) repeat(7, 1fr)', borderBottom: '1px solid #f0ede7', background: insightHover === cluster.id ? '#fafaf8' : 'transparent' }}
                  onMouseEnter={() => setInsightHover(cluster.id)}
                  onMouseLeave={() => setInsightHover(null)}
                >
                  <div style={{ padding: '10px 14px', borderRight: '1px solid #e8e5de', display: 'flex', alignItems: 'center', gap: 6 }}>
                    {statusDot(cluster.today?.status)}
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.2 }}>{cluster.name}</div>
                      <div style={{ fontSize: 10, color: '#a3a398' }}>{Number(cluster.pending_area).toFixed(1)} ac left</div>
                    </div>
                  </div>

                  {(cluster.week_plan ?? []).map((dayPlan: any, dayIdx: number) => (
  <div
    key={dayIdx}
                                        // 👈 add this

  onClick={() => {
  const dayObj = days[dayIdx];
  const clickedDate = new Date(dayObj.date + 'T00:00:00');
  setInsightDetailDate(clickedDate);
  setInsightDetailCluster(cluster);
  setShowInsightDayDetail(true);
  fetchInsightDayData(clickedDate, cluster.id);  // 👈 add this

    }}
    style={{
      padding: '6px 5px',
      borderRight: dayIdx < 6 ? '1px solid #f0ede7' : 'none',
      background: dayIdx === 0 ? 'rgba(16,163,74,0.04)' : 'transparent',
      display: 'flex', flexDirection: 'column', gap: 3,
      justifyContent: 'center', alignItems: 'center',
      minHeight: 44,
      cursor: 'pointer',                                      // 👈 show pointer
    }}
    onMouseEnter={e => (e.currentTarget.style.background = '#f5f5f0')}
    onMouseLeave={e => (e.currentTarget.style.background = dayIdx === 0 ? 'rgba(16,163,74,0.04)' : 'transparent')}
  >
    {/* Confirmed allocations */}
    {dayPlan.teams.length > 0 && dayPlan.teams.map((team: any, ti: number) => (
      <div key={ti} style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '2px 6px', borderRadius: 5, fontSize: 10, fontWeight: 500, background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#1a1a1a', whiteSpace: 'nowrap' }}>
        <span>{team.name.split(' ')[0]}</span>
        {team.crew > 0 && <span style={{ fontSize: 10, fontWeight: 700, background: '#e8e5de', padding: '0 4px', borderRadius: 3, color: '#6b6b63' }}>{team.crew}</span>}
        <span style={typeTagStyle(team.type_tag)}>{team.type_tag}</span>
      </div>
    ))}

    {/* Available (assigned but not yet allocated) — shown dimmed */}
    {/* {dayPlan.teams.length === 0 && (dayPlan.available_teams ?? []).length > 0 && (
      <>
        {dayPlan.available_teams.map((team: any, ti: number) => (
          <div key={ti} style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '2px 6px', borderRadius: 5, fontSize: 10, fontWeight: 500,
            background: '#f8f8f6',           // ← grey tint instead of green
            border: '1px solid #d6d3cc',     // ← muted border
            color: '#9b9b92',                // ← dimmed text
            whiteSpace: 'nowrap',
            opacity: 0.85,
          }}>
            <span>{team.name.split(' ')[0]}</span>
            {team.crew > 0 && <span style={{ fontSize: 10, fontWeight: 700, background: '#e8e5de', padding: '0 4px', borderRadius: 3, color: '#6b6b63' }}>{team.crew}</span>}
            <span style={typeTagStyle(team.type_tag)}>{team.type_tag}</span>
          </div>
        ))}
      </>
    )} */}

    {/* Fallback: no teams and no assigned mukkadams */}
    {dayPlan.teams.length === 0 && (dayPlan.available_teams ?? []).length === 0 && (
      <span style={{ fontSize: 10, color: cluster.pending_area > 0 ? '#dc2626' : '#16a34a', fontWeight: 500, padding: '2px 6px', borderRadius: 4, background: cluster.pending_area > 0 ? '#fef2f2' : 'transparent' }}>
        {cluster.pending_area > 0 ? '—' : '✓'}
      </span>
    )}

    {/* Unallocated badge */}
    {dayPlan.unallocated > 0 && (
      <span style={{ fontSize: 9, fontWeight: 600, color: '#dc2626', background: '#fef2f2', padding: '1px 5px', borderRadius: 4, border: '1px solid #fecaca', lineHeight: '14px', whiteSpace: 'nowrap' }}>
        {dayPlan.unallocated} unalloc
      </span>
    )}
  </div>
))}
                </div>
              ))}

              {/* No cluster row in 7-day grid */}
{insightsData.no_cluster_row && (() => {
  const nc = insightsData.no_cluster_row;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(150px, 180px) repeat(7, 1fr)', borderBottom: '1px solid #fde68a', background: '#fefce8' }}>
      <div style={{ padding: '10px 14px', borderRight: '1px solid #e8e5de', display: 'flex', alignItems: 'center', gap: 6 }}>
        <span>⚠️</span>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#ca8a04' }}>No Cluster</div>
          <div style={{ fontSize: 10, color: '#a3a398' }}>{Number(nc.pending_area).toFixed(1)} ac left</div>
        </div>
      </div>
      {(nc.week_plan ?? []).map((dayPlan: any, dayIdx: number) => (
        <div key={dayIdx} style={{ padding: '6px 5px', borderRight: dayIdx < 6 ? '1px solid #f0ede7' : 'none', display: 'flex', flexDirection: 'column', gap: 3, justifyContent: 'center', alignItems: 'center', minHeight: 44 }}>
          {dayPlan.unallocated > 0 ? (
            <span style={{ fontSize: 9, fontWeight: 600, color: '#dc2626', background: '#fef2f2', padding: '1px 5px', borderRadius: 4, border: '1px solid #fecaca' }}>
              {dayPlan.unallocated} unalloc
            </span>
          ) : (
            <span style={{ fontSize: 10, color: '#16a34a' }}>✓</span>
          )}
        </div>
      ))}
    </div>
  );
})()}

              {/* Summary: Unallocated */}
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(150px, 180px) repeat(7, 1fr)', borderTop: '2px solid #e8e5de', background: '#fef2f2' }}>
                <div style={{ padding: '12px 14px', borderRight: '1px solid #fecaca', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>⚠️</span>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#dc2626' }}>Unallocated</div>
                    <div style={{ fontSize: 10, color: '#6b6b63' }}>total jobs</div>
                  </div>
                </div>
                {daily.map((d: any, dayIdx: number) => (
                  <div key={dayIdx} style={{ padding: '10px 6px', borderRight: dayIdx < 6 ? '1px solid rgba(220,38,38,0.15)' : 'none', background: dayIdx === 0 ? 'rgba(220,38,38,0.06)' : 'transparent', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 800, color: d.unallocated === 0 ? '#16a34a' : d.unallocated > 40 ? '#dc2626' : '#ea580c' }}>
                      {d.unallocated === 0 ? '✓' : d.unallocated}
                    </div>
                    {d.unallocated > 0 && <div style={{ fontSize: 9, color: '#6b6b63', marginTop: 1 }}>jobs</div>}
                  </div>
                ))}
              </div>

              {/* Summary: Crew Deployed */}
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(150px, 180px) repeat(7, 1fr)', background: '#f0fdf4', borderTop: '1px solid #bbf7d0' }}>
                <div style={{ padding: '12px 14px', borderRight: '1px solid #bbf7d0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>👷</span>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#16a34a' }}>Crew Deployed</div>
                    <div style={{ fontSize: 10, color: '#6b6b63' }}>total workers</div>
                  </div>
                </div>
                {daily.map((d: any, dayIdx: number) => (
                  <div key={dayIdx} style={{ padding: '10px 6px', borderRight: dayIdx < 6 ? '1px solid rgba(16,163,74,0.15)' : 'none', background: dayIdx === 0 ? 'rgba(16,163,74,0.06)' : 'transparent', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 800, color: d.crew > 50 ? '#16a34a' : d.crew > 0 ? '#ea580c' : '#dc2626' }}>{d.crew}</div>
                    <div style={{ fontSize: 9, color: '#6b6b63', marginTop: 1 }}>workers</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
{showInsightDayDetail && insightDetailDate && (() => {
  const dateStr = formatDateInsight(insightDetailDate);
  console.log('=== INSIGHT DAY DEBUG ===');
  console.log('dateStr:', dateStr);
  console.log('allActivities length:', allActivities.length);
  console.log('matching activities:', allActivities.filter((a: any) => 
    a.scheduled_date?.slice(0, 10) === dateStr
  ).length);
  console.log('sample activity scheduled_date:', allActivities[0]?.scheduled_date);
  return null;
})()}

{showInsightDayDetail && insightDetailDate && (
  <DayDetailModal
    date={insightDetailDate}
    jobs={(() => {
      const dateStr = formatDateInsight(insightDetailDate);
      const jobMap = new Map<string, any>();
      allActivities
        .filter((a: any) => {
          const dateMatch = a.scheduled_date?.slice(0, 10) === dateStr;
          const clusterMatch = insightDetailCluster
            ? (a.clusters ?? []).some((c: any) => c.id === insightDetailCluster.id) ||
              (a.farmer_clusters ?? []).some((c: any) => c.id === insightDetailCluster.id)
            : true;
          return dateMatch && clusterMatch;
        })
        .forEach((a: any) => {
          if (!jobMap.has(a.job_id)) {
            jobMap.set(a.job_id, {
              job_id:      a.job_id,
              farmer_name: a.farmer_name,
              crop_name:   a.crop_name,
              variety:     a.variety,
              plot_name:   a.plot_name,
              plot_code:   a.plot_code,
              status:      a.job_status,
              activities:  [],
              booking:     null,
            });
          }
          jobMap.get(a.job_id).activities.push({
            id:                a.activity_id,
            activity_id:       a.activity_id,
            activity_name:     a.activity_name,
            name:              a.activity_name,
            scheduled_date:    a.scheduled_date,
            total_area:        a.total_area,
            allocated_area:    a.allocated_area,
            remaining_area:    a.remaining_area,
            allocation_status: a.allocation_status,
            is_manually_moved: a.is_manually_moved,
            plot_name:         a.plot_name,
            plot_code:         a.plot_code,
            rate_per_acre:     a.rate_per_acre,
          });
        });
      return Array.from(jobMap.values());
    })()}
    allocations={insightDayAllocations}
    mukkadams={data?.mukkadams ?? []}  // 👈 pass ALL mukkadams, don't filter — modal uses clusterId to fetch availability itself
    capacitySummary={{
  used:             insightDayAllocations.reduce((s: number, a: any) => s + (a.allocated_workers || 0), 0),
  total:            insightDayMukkadams.reduce((s: number, m: any) => s + (m.available_crew_size || 0), 0),
  percentage:       0,
  conflicts:        [],
  mukkadamsOnLeave: 0,
}}
    leaves={[]}
    overloads={[]}
    onLeavesUpdated={() => {
      if (insightDetailDate && insightDetailCluster?.id) {
        fetchInsightDayData(insightDetailDate, insightDetailCluster.id);
      }
    }}
    onClose={() => {
      setShowInsightDayDetail(false);
      setInsightDetailDate(null);
      setInsightDetailCluster(null);
      setInsightDayAllocations([]);
    }}
    onAllocationDateChange={() => {}}
    onAllocationDelete={() => {}}
    onStartAllocation={() => {}}
    potentialJobs={[]}
    filters={{
      farmerId: null, mukkadamId: null,
      dateFrom: null, dateTo: null,
      plotId: null, activityId: null,
      cropName: null, variety: null,
    }}
    allJobs={[]}
    viewMode={['jobs']}
    clusterId={insightDetailCluster?.id ?? 0}
  />
)}
        </>
      );
    })()}
  </>)
  : tab === 'mukkadams' ? (

          <>
            <table style={{ width: '100%', background: '#fff', borderRadius: 18, boxShadow: S.shadowCard, overflow: 'hidden', borderCollapse: 'separate', borderSpacing: 0 }}>
              <thead>
                <tr>
                  {[
                    { h: 'Mukkadam', pl: 20 },
                    { h: 'Location' },
                    { h: 'Crew',      ac: true },
                    { h: 'Activities', ac: true },
                    { h: 'Cluster' },
                    { h: 'Rate/ac',   ar: true },
                    { h: 'Actions',   ar: true },
                    { h: '' },
                  ].map((col, i) => (
                    <th key={i} style={{ background: 'linear-gradient(180deg,#fafaf9 0%,#f7f6f4 100%)', padding: `10px ${col.pl ?? 14}px`, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, textAlign: col.ac ? 'center' : col.ar ? 'right' : 'left', borderBottom: `2px solid ${S.stone200}`, whiteSpace: 'nowrap', position: 'sticky', top: 0, zIndex: 10 }}>
                      {col.h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredMukkadams.length === 0
                  ? <tr><td colSpan={8} style={{ textAlign: 'center', padding: 48, color: S.stone400 }}>No mukkadams found</td></tr>
                  : filteredMukkadams.map(m => (
                    <MukkadamCard key={m.id} m={m} clusters={clusters} isAdmin={isAdmin} onSuccess={fetchDataSilent}
                      onCallClick={(num: string) => { setDialpadNumber(num || ''); setDialpadOpen(true); }} />
                  ))
                }
              </tbody>
            </table>
            <Dialpad isOpen={dialpadOpen} number={dialpadNumber} onClose={() => setDialpadOpen(false)} onNumberChange={setDialpadNumber} />
          </>
 
        ) : tab === 'farmers' ? (
          <table style={{ width: '100%', background: '#fff', borderRadius: 18, boxShadow: S.shadowCard, overflow: 'hidden', borderCollapse: 'separate', borderSpacing: 0 }}>
            <thead>
              <tr>
                {[
                  { h: 'Farmer',     pl: 20 },
                  { h: 'Location' },
                  { h: 'Plots',      ac: true },
                  { h: 'Jobs',       ac: true },
                  { h: 'Cluster' },
                  { h: 'Activities', ac: true },
                  { h: 'Pruning' },
                  { h: 'Actions',    ar: true },
                  { h: '' },
                ].map((col, i) => (
                  <th key={i} style={{ background: 'linear-gradient(180deg,#fafaf9 0%,#f7f6f4 100%)', padding: `10px ${col.pl ?? 14}px`, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, textAlign: col.ac ? 'center' : col.ar ? 'right' : 'left', borderBottom: `2px solid ${S.stone200}`, whiteSpace: 'nowrap', position: 'sticky', top: 0, zIndex: 10 }}>
                    {col.h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {subTabFilteredFarmers.length === 0
                ? <tr><td colSpan={9} style={{ textAlign: 'center', padding: 48, color: S.stone400 }}>No farmers found</td></tr>
                : subTabFilteredFarmers.map((f: any) => (
                  <FarmerCard key={f.farmer_id} farmer={f} clusters={clusters} isAdmin={isAdmin} onSuccess={fetchDataSilent} />
                ))
              }
            </tbody>
          </table>
 
        ) : tab === 'jobs' ? (
          <>
            {actLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '64px 0' }}>
                <RefreshCw size={28} style={{ color: S.brand, animation: 'spin 1s linear infinite' }} />
              </div>
            ) : activities.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '64px 0', color: S.stone400 }}>No activities found</div>
            ) : (() => {
              // group by activity_name
              const grouped: Record<string, any[]> = {};
              activities.forEach((a: any) => {
                const k = a.activity_name || 'Unknown';
                if (!grouped[k]) grouped[k] = [];
                grouped[k].push(a);
              });
 
              return Object.entries(grouped).map(([actName, acts]) => {
                const totalArea  = acts.reduce((s: number, a: any) => s + Number(a.total_area || 0), 0);
                const totalValue = acts.reduce((s: number, a: any) => s + Number(a.total_price || 0), 0);
                const unalloc    = acts.filter((a: any) => a.allocation_status === 'pending').length;
                const ov30       = acts.filter((a: any) => a.days_until !== null && a.days_until < -30).length;
                const ov7        = acts.filter((a: any) => a.days_until !== null && a.days_until >= -30 && a.days_until < -7).length;
 
                return (
                  <GroupedActivitySection
                    key={actName}
                    actName={actName}
                    acts={acts}
                    totalArea={totalArea}
                    totalValue={totalValue}
                    unalloc={unalloc}
                    ov30={ov30}
                    ov7={ov7}
                    expandedActJob={expandedActJob}
                    setExpandedActJob={setExpandedActJob}
                    isAdmin={isAdmin}
                    handleUpdownComplete={handleUpdownComplete}
                    maxWorkRows={jobsMaxWorkRows}
                    onAllocate={async (act: any, isoDate: string) => {
                      // Open dialog immediately with loading state
                      setAllocDialog({
                        open: true,
                        act,
                        job: { job_id: act.job_id, farmer_name: act.farmer_name },
                        isoDate,
                        mukkadams: [],
                        loadingMukkadams: true,
                      });
                      // fetchJobsCapacity fetches capacity + mukkadam details,
                      // enriches them, and calls setAllocDialog with the result
                      await fetchJobsCapacity(isoDate, act);
                    }}
                    onAllocateWithMukkadam={(act: any, workerRow: any, isoDate: string, remainingArea: number, slotsUsed: number) => {
                      setJobsHalfDayDialog({
                        open: true,
                        jobId: act.job_id,
                        act,
                        mukkadam: workerRow.mukkadamObj,
                        rate: workerRow.rate,
                        availableWorkers: workerRow.availableWorkers,
                        neededWorkers: 0,
                        remainingArea,
                        isSecondJob: slotsUsed >= 1,
                        jobSlotsUsed: slotsUsed,
                        targetDate: isoDate,
                      });
                    }}
                    jobNotes={jobNotes}
                    onSuccess={fetchDataSilent}
                    onNote={(jobId: string, label: string) => {
                      setJobsNoteJobId(jobId);
                      setJobsNoteJobLabel(label);
                    }}
                  />
                );
              });
            })()}
          </>
 
        ) : null}
      </div>

      {/* ══════ ALLOCATE DIALOG ══════ */}
      {allocDialog?.open && ReactDOM.createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 99999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
          onClick={() => setAllocDialog(null)}>
          <div style={{ background: '#fff', borderRadius: 16, width: 480, maxHeight: '80vh', overflowY: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,.25)' }}
            onClick={e => e.stopPropagation()}>

            {/* Header */}
            <div style={{ padding: '18px 22px', borderBottom: `1px solid ${S.stone200}` }}>
              <div style={{ fontWeight: 700, fontSize: 15, color: S.stone900 }}>
                Allocate — {allocDialog.act.activity_name}
              </div>
              <div style={{ fontSize: 12, color: S.stone500, marginTop: 3 }}>
                {allocDialog.job.farmer_name} · {allocDialog.act.total_area} ac · {allocDialog.isoDate}
              </div>
            </div>

            <div style={{ padding: '16px 22px' }}>
              {allocDialog.loadingMukkadams ? (
                <div style={{ textAlign: 'center', padding: '32px 0', color: S.stone400, fontSize: 13 }}>
                  Loading mukkadams...
                </div>
              ) : allocDialog.mukkadams.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 0' }}>
                  <div style={{ fontSize: 24, marginBottom: 8 }}>⚠️</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: S.stone700 }}>No mukkadams in this cluster</div>
                  <div style={{ fontSize: 12, color: S.stone400, marginTop: 4 }}>Add mukkadams to the cluster first</div>
                </div>
              ) : (
                <>
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, marginBottom: 10 }}>
                    Select Mukkadam
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {allocDialog.mukkadams.map((mk: any) => {
                      // capacity for this activity on this date
                      const actRate = mk.rate ?? mk.activity_rates?.find(
                        (r: any) => r.activity_id === allocDialog.act.activity_id || r.activity_name === allocDialog.act.activity_name,
                      );
                      // Try multiple field names the API might return
                      const availCrew   = mk.available_crew_size ?? mk.crew_size ?? 0;
                      const canDoAc     = Number(mk.max_area ?? 0);
                      const remainingArea = Number(allocDialog.act.remaining_area ?? allocDialog.act.total_area ?? 0);
                      const isOnHoliday = availCrew === 0;
                      const fits        = !isOnHoliday && canDoAc > 0 && canDoAc >= remainingArea;
                      // count existing allocations for this mukkadam on this date
                      const slotsUsed = (data?.farmers ?? [])
                        .flatMap((f: any) => f.jobs ?? [])
                        .flatMap((j: any) => j.activities ?? [])
                        .flatMap((a: any) => a.allocations ?? [])
                        .filter((al: any) => al.mukkadam_id === mk.mukkadam_id && al.allocated_date === allocDialog.isoDate)
                        .length;

                      return (
                        <button key={mk.mukkadam_id}
                          onClick={() => {
                            setAllocHalfDay({
                              open: true,
                              act: allocDialog.act,
                              job: allocDialog.job,
                              mukkadam: mk,
                              rate: actRate,
                              availableWorkers: mk.available_crew_size ?? mk.crew_size ?? 0,
                              remainingArea,
                              isoDate: allocDialog.isoDate,
                              jobSlotsUsed: slotsUsed,
                            });
                          }}
                          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', borderRadius: 12, border: `1.5px solid ${fits ? S.green100 : S.stone200}`, background: fits ? S.green50 : '#fff', cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left', transition: 'all 150ms' }}
                          onMouseEnter={e => (e.currentTarget.style.borderColor = fits ? S.green700 : S.stone400)}
                          onMouseLeave={e => (e.currentTarget.style.borderColor = fits ? S.green100 : S.stone200)}
                        >
                          <div>
                            <div style={{ fontWeight: 700, fontSize: 13, color: S.stone900 }}>
                              👷 {mk.mukkadam_name || mk.name || mk.mukkadam?.mukkadam_name || `ID: ${mk.mukkadam_id}`}
                            </div>
                            <div style={{ fontSize: 11, color: S.stone500, marginTop: 2 }}>
                              Crew: {mk.crew_size ?? mk.available_crew_size ?? '—'} · {mk.mobile_numbers || mk.mobile || '—'}
                              {slotsUsed > 0 && <span style={{ marginLeft: 6, color: '#0369a1', fontWeight: 600 }}>{slotsUsed} job{slotsUsed > 1 ? 's' : ''} today</span>}
                            </div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 999, background: canDoAc === 0 ? S.stone100 : fits ? S.green50 : '#fff1f2', color: canDoAc === 0 ? S.stone400 : fits ? S.green700 : S.red700, border: `1px solid ${canDoAc === 0 ? S.stone200 : fits ? S.green100 : S.red100}` }}>
                              {isOnHoliday ? '🏖️ Holiday' : `${remainingArea.toFixed(2)} needed / ${canDoAc.toFixed(2)} can do`}
                            </div>
                            {actRate && <div style={{ fontSize: 10, color: S.stone400, marginTop: 3 }}>₹{actRate.rate_per_acre}/ac</div>}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
            </div>

            <div style={{ padding: '12px 22px', borderTop: `1px solid ${S.stone200}`, display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setAllocDialog(null)}
                style={{ padding: '8px 18px', borderRadius: 8, border: `1px solid ${S.stone200}`, background: '#fff', color: S.stone600, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
                Cancel
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* ══════ HALF-DAY CONFIRM DIALOG ══════ */}
      {allocHalfDay?.open && ReactDOM.createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 999999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => { setAllocHalfDay(null); setAllocAllowsMore(false); }}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, width: 360, boxShadow: '0 20px 60px rgba(0,0,0,.25)' }}
            onClick={e => e.stopPropagation()}>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 700, fontSize: 15, color: S.stone900 }}>Confirm Allocation</div>
              <div style={{ fontSize: 12, color: S.stone500, marginTop: 3 }}>
                {allocHalfDay.act.activity_name} → {allocHalfDay.mukkadam.mukkadam_name}
              </div>
            </div>

            {/* Summary */}
            <div style={{ background: '#f9fafb', borderRadius: 10, padding: 12, fontSize: 12, color: '#374151', marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                ['Area',              `${allocHalfDay.remainingArea.toFixed(2)} ac`],
                ['Workers available', `${allocHalfDay.availableWorkers} workers`],
                ['Rate',              `₹${Number(allocHalfDay.rate?.rate_per_acre || 0).toFixed(0)}/ac`],
                ['Date',              allocHalfDay.isoDate],
              ].map(([label, value]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#6b7280' }}>{label}</span>
                  <span style={{ fontWeight: 700 }}>{value}</span>
                </div>
              ))}
            </div>

            {/* ⅓ day slot banner — same logic as DayDetailModal */}
            {(() => {
              const slotsUsed = allocHalfDay.jobSlotsUsed ?? 0;
              if (slotsUsed >= 2) return (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: 10, border: '2px solid #0ea5e9', background: '#f0f9ff', marginBottom: 16 }}>
                  <span style={{ fontSize: 16, flexShrink: 0 }}>⅓</span>
                  <div>
                    <div style={{ margin: 0, fontWeight: 700, fontSize: 12, color: '#0369a1' }}>3rd job — full day used</div>
                    <div style={{ margin: '3px 0 0', fontSize: 11, color: '#0284c7', lineHeight: 1.5 }}>
                      {allocHalfDay.mukkadam.mukkadam_name} already has 2 jobs today. This final ⅓ completes their day.
                    </div>
                  </div>
                </div>
              );
              if (slotsUsed === 1) return (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: 10, border: '2px solid #0ea5e9', background: '#f0f9ff', marginBottom: 16 }}>
                  <span style={{ fontSize: 16, flexShrink: 0 }}>⅓</span>
                  <div>
                    <div style={{ margin: 0, fontWeight: 700, fontSize: 12, color: '#0369a1' }}>2nd job — 1 slot remaining</div>
                    <div style={{ margin: '3px 0 0', fontSize: 11, color: '#0284c7', lineHeight: 1.5 }}>
                      {allocHalfDay.mukkadam.mukkadam_name} has 1 job today. After this, 1 more ⅓-day slot remains.
                    </div>
                  </div>
                </div>
              );
              return (
                <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: 10, cursor: 'pointer', border: `2px solid ${allocAllowsMore ? '#10b981' : S.stone200}`, background: allocAllowsMore ? '#f0fdf4' : '#fff', marginBottom: 16, transition: 'all 150ms' }}>
                  <input type="checkbox" checked={allocAllowsMore} onChange={e => setAllocAllowsMore(e.target.checked)}
                    style={{ marginTop: 2, accentColor: '#10b981', width: 16, height: 16, flexShrink: 0 }} />
                  <div>
                    <div style={{ margin: 0, fontWeight: 700, fontSize: 12, color: '#065f46' }}>⅓ Can do more jobs today</div>
                    <div style={{ margin: '3px 0 0', fontSize: 11, color: '#6b7280', lineHeight: 1.5 }}>
                      Runs in 1 of 3 slots — workers stay available for up to 2 more ⅓-day jobs. Count will <strong>not</strong> be deducted from daily capacity.
                    </div>
                  </div>
                </label>
              );
            })()}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => { setAllocHalfDay(null); setAllocAllowsMore(false); }}
                style={{ padding: '8px 18px', borderRadius: 8, border: `1px solid ${S.stone200}`, background: '#fff', color: '#374151', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}>
                Cancel
              </button>
              <button onClick={handleConfirmAllocate}
                style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: allocAllowsMore ? '#10b981' : '#2563eb', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', transition: 'background 150ms' }}>
                {allocAllowsMore ? '⅓ Allocate' : 'Allocate'}
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* ══════ MOVE DIALOG ══════ */}
      {moveDialog && ReactDOM.createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 99999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => setMoveDialog(null)}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, width: 360, boxShadow: '0 20px 60px rgba(0,0,0,.25)' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ fontWeight: 700, fontSize: 15, color: S.stone900, marginBottom: 4 }}>Move Activity</div>
            <div style={{ fontSize: 12, color: S.stone500, marginBottom: 16 }}>
              {moveDialog.act.activity_name} · {moveDialog.job.farmer_name}
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: S.stone600, display: 'block', marginBottom: 5 }}>New Date <span style={{ color: '#ef4444' }}>*</span></label>
              <input type="date" value={moveDate} onChange={e => setMoveDate(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: `1.5px solid ${S.stone200}`, fontSize: 13, fontFamily: 'inherit', boxSizing: 'border-box' }} />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: S.stone600, display: 'block', marginBottom: 5 }}>Reason (optional)</label>
              <input type="text" value={moveReason} onChange={e => setMoveReason(e.target.value)}
                placeholder="e.g. Farmer not available"
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: `1.5px solid ${S.stone200}`, fontSize: 13, fontFamily: 'inherit', boxSizing: 'border-box' }} />
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setMoveDialog(null)}
                style={{ padding: '8px 18px', borderRadius: 8, border: `1px solid ${S.stone200}`, background: '#fff', color: S.stone600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                Cancel
              </button>
              <button onClick={handleMoveJob} disabled={!moveDate || moveSaving}
                style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: !moveDate || moveSaving ? S.stone300 : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 700, cursor: !moveDate || moveSaving ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}>
                {moveSaving ? 'Moving...' : '↩ Move'}
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* ══════ NOTE DIALOG ══════ */}
      {noteDialog && ReactDOM.createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 99999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => setNoteDialog(null)}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, width: 400, boxShadow: '0 20px 60px rgba(0,0,0,.25)' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ fontWeight: 700, fontSize: 15, color: S.stone900, marginBottom: 4 }}>Add Note</div>
            <div style={{ fontSize: 12, color: S.stone500, marginBottom: 16 }}>{noteDialog.label}</div>

            <textarea
              value={noteText}
              onChange={e => setNoteText(e.target.value)}
              placeholder="Type your note here..."
              rows={4}
              style={{ width: '100%', padding: '10px 12px', borderRadius: 10, border: `1.5px solid ${S.stone200}`, fontSize: 13, fontFamily: 'inherit', resize: 'vertical', boxSizing: 'border-box', outline: 'none' }}
              onFocus={e => (e.target.style.borderColor = S.brand)}
              onBlur={e  => (e.target.style.borderColor = S.stone200)}
            />

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
              <button onClick={() => setNoteDialog(null)}
                style={{ padding: '8px 18px', borderRadius: 8, border: `1px solid ${S.stone200}`, background: '#fff', color: S.stone600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                Cancel
              </button>
              <button onClick={handleSaveNote} disabled={!noteText.trim() || noteSaving}
                style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: !noteText.trim() || noteSaving ? S.stone300 : S.violet600, color: '#fff', fontSize: 13, fontWeight: 700, cursor: !noteText.trim() || noteSaving ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}>
                {noteSaving ? 'Saving...' : '✏️ Save Note'}
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* ══════ JOBS TAB: ⅓-DAY CONFIRM DIALOG ══════ */}
      {jobsHalfDayDialog?.open && ReactDOM.createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 99999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => { setJobsHalfDayDialog(null); setJobsAllowsMoreJobs(false); }}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, width: 360, boxShadow: '0 20px 60px rgba(0,0,0,.25)' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 700, fontSize: 15, color: '#111827' }}>Confirm Allocation</div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 3 }}>
                {jobsHalfDayDialog.act.activity_name} → {jobsHalfDayDialog.mukkadam.mukkadam_name}
              </div>
            </div>
            <div style={{ background: '#f9fafb', borderRadius: 10, padding: 12, fontSize: 12, color: '#374151', marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                ['Area',              `${jobsHalfDayDialog.remainingArea.toFixed(2)} ac`],
                ['Workers available', `${jobsHalfDayDialog.availableWorkers} workers`],
                ['Rate',              `₹${Number(jobsHalfDayDialog.rate?.rate_per_acre || 0).toFixed(0)}/ac`],
                ['Date',              jobsHalfDayDialog.targetDate],
              ].map(([label, value]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#6b7280' }}>{label}</span>
                  <span style={{ fontWeight: 700 }}>{value}</span>
                </div>
              ))}
            </div>
            {(() => {
              const slotsUsed = jobsHalfDayDialog.jobSlotsUsed ?? 0;
              if (slotsUsed >= 2) return (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: 10, border: '2px solid #0ea5e9', background: '#f0f9ff', marginBottom: 16 }}>
                  <span style={{ fontSize: 16, flexShrink: 0 }}>⅓</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 12, color: '#0369a1' }}>3rd job — full day used</div>
                    <div style={{ fontSize: 11, color: '#0284c7', lineHeight: 1.5, marginTop: 3 }}>
                      {jobsHalfDayDialog.mukkadam.mukkadam_name} already has 2 jobs today. This completes their day.
                    </div>
                  </div>
                </div>
              );
              if (slotsUsed === 1) return (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: 10, border: '2px solid #0ea5e9', background: '#f0f9ff', marginBottom: 16 }}>
                  <span style={{ fontSize: 16, flexShrink: 0 }}>⅓</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 12, color: '#0369a1' }}>2nd job — 1 slot remaining</div>
                    <div style={{ fontSize: 11, color: '#0284c7', lineHeight: 1.5, marginTop: 3 }}>
                      {jobsHalfDayDialog.mukkadam.mukkadam_name} has 1 job today. 1 more slot after this.
                    </div>
                  </div>
                </div>
              );
              return (
                <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: 10, cursor: 'pointer', border: `2px solid ${jobsAllowsMoreJobs ? '#10b981' : '#e5e7eb'}`, background: jobsAllowsMoreJobs ? '#f0fdf4' : '#fff', marginBottom: 16, transition: 'all 150ms' }}>
                  <input type="checkbox" checked={jobsAllowsMoreJobs} onChange={e => setJobsAllowsMoreJobs(e.target.checked)}
                    style={{ marginTop: 2, accentColor: '#10b981', width: 16, height: 16, flexShrink: 0 }} />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 12, color: '#065f46' }}>⅓ Can do more jobs today</div>
                    <div style={{ fontSize: 11, color: '#6b7280', lineHeight: 1.5, marginTop: 3 }}>
                      1 of 3 slots — workers stay available for 2 more ⅓-day jobs. Count <strong>not</strong> deducted from capacity.
                    </div>
                  </div>
                </label>
              );
            })()}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => { setJobsHalfDayDialog(null); setJobsAllowsMoreJobs(false); }}
                style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}>
                Cancel
              </button>
              <button onClick={handleJobsConfirmAllocation}
                style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: jobsAllowsMoreJobs ? '#10b981' : '#2563eb', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>
                {jobsAllowsMoreJobs ? '⅓ Allocate' : 'Allocate'}
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* ══════ JOBS TAB: NOTE MODAL ══════ */}
      {jobsNoteJobId && (
        <JobNoteModal
          jobId={jobsNoteJobId}
          jobLabel={jobsNoteJobLabel}
          noteDate={new Date().toISOString().slice(0, 10)}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          clusterId={Number(
            activities.find((a: any) => a.job_id === jobsNoteJobId)
              ?.farmer_clusters?.[0]?.id ??
            clusterFilter ??
            clusterId ??
            0
          )}
          onClose={() => setJobsNoteJobId(null)}
        />
      )}

      {/* ══════ JOBS TAB: MOVE JOB DIALOG ══════ */}
      {moveDialog && ReactDOM.createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 99999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => setMoveDialog(null)}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, width: 340, boxShadow: '0 20px 60px rgba(0,0,0,.25)' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ fontWeight: 700, fontSize: 15, color: '#111827', marginBottom: 4 }}>Move Job Activity</div>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 16 }}>
              {moveDialog.act.activity_name} · {moveDialog.job?.farmer_name}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 5 }}>New Date</label>
                <input type="date" value={moveDate} onChange={e => setMoveDate(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #e5e7eb', fontSize: 13, fontFamily: 'inherit', boxSizing: 'border-box' }} />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 5 }}>
                  Area to Move (ac) <span style={{ color: '#a8a29e', fontWeight: 400 }}>max: {moveDialog.act.remaining_area ?? moveDialog.act.total_area} ac</span>
                </label>
                <input type="number" step="0.01" min="0.01" max={moveDialog.act.remaining_area ?? moveDialog.act.total_area}
                  value={moveArea}
                  onChange={e => setMoveArea(e.target.value)}
                  placeholder={String(moveDialog.act.remaining_area ?? moveDialog.act.total_area ?? '')}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #e5e7eb', fontSize: 13, fontFamily: 'inherit', boxSizing: 'border-box' }} />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
                  Reason <span style={{ color: '#ef4444' }}>*</span>
                </label>
                {['Not strict job — can reschedule', 'Easy farmer — farmer agreed to move'].map(r => (
                  <button key={r} type="button" onClick={() => setMoveReason(r)}
                    style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', borderRadius: 8, border: `1.5px solid ${moveReason === r ? '#f97316' : '#e5e7eb'}`, background: moveReason === r ? '#fff7ed' : '#f9fafb', color: moveReason === r ? '#c2410c' : '#57534e', fontSize: 12, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit', marginBottom: 6 }}>
                    {moveReason === r ? '✓ ' : ''}{r}
                  </button>
                ))}
                <textarea value={moveReason} onChange={e => setMoveReason(e.target.value)}
                  placeholder="Or type a custom reason..."
                  rows={2}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #e5e7eb', fontSize: 12, fontFamily: 'inherit', resize: 'none', boxSizing: 'border-box' }} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>
              <button onClick={() => setMoveDialog(null)}
                style={{ flex: 1, padding: '9px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', color: '#57534e', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                Cancel
              </button>
              <button
                disabled={!moveDate || !moveReason.trim() || moveSaving}
                onClick={handleMoveJob}
                style={{ flex: 1, padding: '9px', borderRadius: 8, border: 'none', background: !moveDate || !moveReason.trim() || moveSaving ? '#d6d3d1' : '#f97316', color: '#fff', fontSize: 13, fontWeight: 700, cursor: !moveDate || !moveReason.trim() || moveSaving ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}>
                {moveSaving ? 'Moving...' : 'Confirm Move'}
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}
 
      {/* AddToClusterModal */}
      {clusterModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 10000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => setClusterModal(null)}>
          <div style={{ background: '#fff', borderRadius: 14, padding: '2rem', boxShadow: '0 24px 60px rgba(0,0,0,.25)' }}
            onClick={e => e.stopPropagation()}>
            {clusterModal && (
              <AddToClusterModal clusterId={clusterModal.clusterId} clusterName={clusterModal.clusterName} mode="farmer"
                onClose={() => { setClusterModal(null); fetchData(); }} />
            )}
            <button onClick={() => setClusterModal(null)}
              style={{ marginTop: 16, padding: '8px 16px', background: S.stone100, borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13 }}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
 
// ─────────────────────────────────────────────────────────────────────────────
// GROUPED ACTIVITY SECTION  — new helper component used by Jobs tab above
// Paste this OUTSIDE TenderDashboard, near MukkadamCard / FarmerCard
// ─────────────────────────────────────────────────────────────────────────────
function GroupedActivitySection({ actName, acts, totalArea, totalValue, unalloc, ov30, ov7, expandedActJob, setExpandedActJob, isAdmin, handleUpdownComplete, onAllocate, onAllocateWithMukkadam, onNote, maxWorkRows, onSuccess, jobNotes }:{
   actName: string; acts: any[]; totalArea: number; totalValue: number;
  unalloc: number; ov30: number; ov7: number;
  expandedActJob: string | null; setExpandedActJob: (id: string | null) => void;
  isAdmin: boolean;
  handleUpdownComplete: (mId: number, aId: number) => void;

  onAllocate: (act: any, isoDate: string) => Promise<void>;
  onAllocateWithMukkadam: (act: any, workerRow: any, isoDate: string, remainingArea: number, slotsUsed: number) => void;
  onNote: (jobId: string, label: string) => void;
  maxWorkRows: any[];
  onSuccess: () => void;
  jobNotes: Record<string, any[]>;
}) {
  const [open, setOpen] = useState(true);

  // compute worker rows for each activity row (same as DayDetailModal maxWorkRows filter)
  const getWorkerRows = (activityName: string) =>
    maxWorkRows.filter((r: any) => r.activityName === activityName);

  return (
    <div style={{ marginBottom: 16, borderRadius: 18, overflow: 'hidden', boxShadow: S.shadowCard }}>
 
      {/* Group header */}
      <div onClick={() => setOpen(!open)}
        style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 20px', background: 'linear-gradient(135deg,#fafaf9 0%,#fff 50%,#fafaf9 100%)', cursor: 'pointer', borderBottom: open ? `1px solid ${S.stone200}` : 'none', position: 'relative', transition: 'background 150ms' }}
        onMouseEnter={e => (e.currentTarget.style.background = S.stone50)}
        onMouseLeave={e => (e.currentTarget.style.background = 'linear-gradient(135deg,#fafaf9 0%,#fff 50%,#fafaf9 100%)')}>
        {/* Left accent */}
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 4, background: 'linear-gradient(135deg,#059669 0%,#0d9488 100%)', borderRadius: '0 2px 2px 0', opacity: open ? 1 : .35 }} />
        {/* Chevron */}
        <div style={{ width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', background: S.stone100, borderRadius: 6, fontSize: 12, color: S.stone400, transition: 'transform 250ms', transform: open ? 'none' : 'rotate(-90deg)', flexShrink: 0 }}>▾</div>
        {/* Name */}
        <div style={{ fontWeight: 800, fontSize: 16, letterSpacing: '-.3px' }}>{actName}</div>
        {/* Stats */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginLeft: 'auto' }}>
          {[
            { val: acts.length,              lbl: 'Jobs'        },
            { val: `${totalArea.toFixed(1)} ac`, lbl: 'Area'   },
            { val: unalloc,                  lbl: 'Unallocated' },
            { val: totalValue >= 100000
                ? `₹${(totalValue / 100000).toFixed(1)}L`
                : `₹${Math.round(totalValue).toLocaleString('en-IN')}`,
              lbl: 'Value', color: S.green700 },
          ].map((s, i) => (
            <div key={i} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 14, fontWeight: 800, lineHeight: 1, color: (s as any).color || S.stone900 }}>{s.val}</div>
              <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.5px', color: S.stone400, marginTop: 2 }}>{s.lbl}</div>
            </div>
          ))}
          {ov30 > 0 && <span style={{ padding: '4px 14px', borderRadius: 999, fontSize: 11, fontWeight: 700, background: S.red50, color: S.red700, border: `1px solid ${S.red100}`, whiteSpace: 'nowrap' }}>{ov30} Overdue 30d+</span>}
          {ov7  > 0 && <span style={{ padding: '4px 14px', borderRadius: 999, fontSize: 11, fontWeight: 700, background: S.amber50, color: S.amber700, border: `1px solid ${S.amber100}`, whiteSpace: 'nowrap' }}>{ov7} Overdue 7-30d</span>}
        </div>
      </div>
 
      {/* Inner table */}
      {open && (
        <table style={{ width: '100%', background: '#fff', borderCollapse: 'separate', borderSpacing: 0 }}>
          <thead>
            <tr>
              {[
                { h: '', w: 28, pl: 20 },
                { h: 'Farmer' },
                { h: 'Plot' },
                { h: 'Location' },
                { h: 'Acres', ar: true },
                { h: 'Scheduled' },
                { h: 'Rate', ar: true },
                { h: 'Cost', ar: true },
                { h: 'Status' },
                { h: 'Action', ac: true },
                { h: '' },
              ].map((col, i) => (
                <th key={i} style={{ background: 'linear-gradient(180deg,#fafaf9 0%,#f7f6f4 100%)', padding: `8px ${col.pl ?? 14}px`, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, textAlign: col.ac ? 'center' : col.ar ? 'right' : 'left', borderBottom: `2px solid ${S.stone200}`, whiteSpace: 'nowrap', width: col.w }}>
                  {col.h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {acts.map((a: any) => {
              console.log(acts[0])
              const isExp       = expandedActJob === String(a.activity_id);
              const isPending   = a.allocation_status === 'pending';
              const isCompleted = a.allocations?.some((al: any) => al.work_status === 'completed');
              const isUpcoming  = a.days_until !== null && a.days_until >= 0  && a.days_until <= 10;
              const isOverdue   = a.days_until !== null && a.days_until < 0   && !isCompleted;
              const overdueDays = a.days_until !== null ? Math.abs(a.days_until) : 0;
              const workerTeamRows = getWorkerRows(a.activity_name);
 const rowNotes: any[] = jobNotes[a.job_id] ?? [];
                  const unresolvedNotes = rowNotes.filter((n: any) => !n.is_resolved);
                  const resolvedNotes   = rowNotes.filter((n: any) => n.is_resolved);
              const dotColor = isPending ? S.amber500 : isCompleted ? S.brand : S.sky600;
              const tdR: React.CSSProperties = { padding: '10px 14px', borderBottom: isExp ? 'none' : `1px solid ${S.stone100}`, verticalAlign: 'middle', fontSize: 12 };
 
              return (
                <React.Fragment key={a.activity_id}>
                  <tr style={{ cursor: 'pointer', background: isExp ? S.brandLight : 'transparent', transition: 'background 150ms' }}
                    onMouseEnter={e => { if (!isExp) (e.currentTarget as HTMLElement).style.background = S.stone25; }}
                    onMouseLeave={e => { if (!isExp) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                    onClick={() => setExpandedActJob(isExp ? null : String(a.activity_id))}>
 
                    {/* dot */}
                    <td style={{ ...tdR, paddingLeft: 20, width: 28 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', display: 'inline-block', background: dotColor, boxShadow: `0 0 0 3px ${dotColor}33` }} />
                    </td>
                    {/* farmer */}
                    <td style={{ ...tdR }}>
                      <div style={{ fontWeight: 700, fontSize: 13, color: S.stone900 }}>{a.farmer_name}</div>
                      <div style={{ fontFamily: S.mono, fontSize: 10, color: S.stone400, marginTop: 2 }}>{a.farmer_phone || '—'}</div>
                    </td>
                    {/* plot */}
                    <td style={{ ...tdR, fontFamily: S.mono, fontWeight: 700, fontSize: 12 }}>{a.plot_code || a.plot_name}</td>
                    {/* location */}
                    <td style={{ ...tdR, color: S.stone600 }}>{a.clusters?.[0]?.name || '—'}</td>
                    {/* acres */}
                    <td style={{ ...tdR, textAlign: 'right', fontWeight: 700, fontSize: 13 }}>{Number(a.total_area).toFixed(2)}</td>
                    {/* scheduled */}
                    <td style={{ ...tdR }}>
                      <span style={{ fontSize: 12 }}>{a.scheduled_date ? a.scheduled_date.slice(5) : '—'}</span>
                      {isOverdue && <div style={{ fontSize: 10, fontWeight: 700, color: overdueDays > 30 ? S.red600 : S.amber700, marginTop: 1 }}>{overdueDays}d overdue</div>}
                      {isUpcoming && <div style={{ fontSize: 10, fontWeight: 700, color: S.amber700, marginTop: 1 }}>In {a.days_until}d</div>}
                    </td>
                    {/* rate */}
                    <td style={{ ...tdR, textAlign: 'right', fontFamily: S.mono, fontSize: 11 }}>₹{Number(a.rate_per_acre).toLocaleString('en-IN')}/ac</td>
                    {/* cost */}
                    <td style={{ ...tdR, textAlign: 'right', fontFamily: S.mono, fontWeight: 800, fontSize: 13 }}>₹{Math.round(Number(a.total_price)).toLocaleString('en-IN')}</td>
                    {/* status */}
                    <td style={{ ...tdR }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 999, fontSize: 11, fontWeight: 700, background: isPending ? S.amber50 : isCompleted ? S.green50 : S.sky50, color: isPending ? S.amber700 : isCompleted ? S.green700 : S.sky700, border: `1px solid ${isPending ? S.amber100 : isCompleted ? S.green100 : S.sky100}`, letterSpacing: '.2px' }}>
                        {isPending ? 'Pending' : isCompleted ? 'Completed' : a.allocation_status === 'fully_allocated' ? 'Allocated' : a.allocation_status.replace('_', ' ')}
                      </span>
                      {a.is_split && <span style={{ marginLeft: 4, fontSize: 10, padding: '1px 6px', borderRadius: 999, background: '#f5f3ff', color: S.violet700, fontWeight: 700 }}>🔀 Split</span>}
                    {/* Notes badge */}
                      {rowNotes.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700, background: unresolvedNotes.length > 0 ? '#fef2f2' : '#f0fdf4', color: unresolvedNotes.length > 0 ? '#be123c' : '#047857', border: `1px solid ${unresolvedNotes.length > 0 ? '#fecaca' : '#bbf7d0'}` }}>
                            ✏️ {unresolvedNotes.length > 0 ? `${unresolvedNotes.length} open` : `${rowNotes.length} note${rowNotes.length > 1 ? 's' : ''}`}
                          </span>
                        </div>
                      )}</td>

                    

                    {/* ── Team / Capacity ── */}
                    <td style={{ ...tdR }} onClick={e => e.stopPropagation()}>
                      {a.allocations?.length > 0 ? (
                        // Already allocated — show mukkadam names
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                          {(a.allocations || []).map((alloc: any, ai: number) => (
                            <div key={ai} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
                              <span style={{ fontWeight: 600 }}>👷 {alloc.mukkadam_name}</span>
                              <span style={{ color: S.stone400 }}>{Number(alloc.allocated_area).toFixed(2)} ac</span>
                              {alloc.allows_second_job && (
                                <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 999, background: '#ecfdf5', color: '#047857', border: '1px solid #d1fae5', fontWeight: 700 }}>⅓</span>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (workerTeamRows).length === 0 ? (
                        <span style={{ fontSize: 11, color: S.stone400, fontStyle: 'italic' }}>No team data</span>
                      ) : (
                        // Show available mukkadams as clickable buttons
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {workerTeamRows.map((r: any, ri: number) => {
                            const canDoAc = Number(r.maxArea || 0);
                            const fits = Number(a.remaining_area ?? a.total_area ?? 0) > 0 && canDoAc >= Number(a.remaining_area ?? a.total_area ?? 0);
                            const isoDate = a.scheduled_date?.slice(0, 10) ?? '';
                            
                            return (
                              <button
                                key={ri}
                                type="button"
                                onClick={() => {
                                  const thirdDayJobsToday = 0; // no alloc context here
                                  onAllocateWithMukkadam(a, r, isoDate, remainingArea, thirdDayJobsToday);
                                }}
                                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 999, fontSize: 11, border: `1px solid ${fits ? '#a7f3d0' : '#fecaca'}`, background: fits ? '#ecfdf5' : '#fff1f2', color: fits ? '#047857' : '#be123c', cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600 }}
                              >
                                <span>{r.mukkadamName}</span>
                                <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 999, background: canDoAc === 0 ? S.stone100 : fits ? '#d1fae5' : '#ffe4e6', color: canDoAc === 0 ? S.stone400 : fits ? '#047857' : '#be123c', fontWeight: 700 }}>
                                  {canDoAc === 0 ? '🏖️ Holiday' : `${remainingArea.toFixed(2)} / ${canDoAc.toFixed(2)} ac`}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </td>
                    {/* action */}
                    {/* ── Action: Allocate / Move / Note / Cancel ── */}
<td style={{ ...tdR, textAlign: 'right', paddingRight: 16 }} onClick={e => e.stopPropagation()}>
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
    {isCompleted ? (
      <span style={{ fontSize: 11, color: S.green700, fontWeight: 700 }}>✅ Done</span>
    ) : isPending ? (
      <button
        onClick={async () => {
          const isoDate = a.scheduled_date?.slice(0, 10) ?? '';
          await onAllocate(a, isoDate);
        }}
        style={{ padding: '5px 12px', borderRadius: 8, background: S.stone800, color: '#fff', border: 'none', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', letterSpacing: '.2px' }}
      >
        Allocate
      </button>
    ) : (
      <CompleteAllocationsButton
        allocations={a.allocations ?? []}
        activityName={a.activity_name}
        farmerName={a.farmer_name}
        onSuccess={onSuccess}
      />
    )}
    <MoveJobButtonTender act={a} onSuccess={onSuccess} />
    <button
      onClick={() => {
        const label = [a.activity_name, a.farmer_name, a.plot_name ? `📍 ${a.plot_name}` : null].filter(Boolean).join(' – ');
        onNote(a.job_id, label);
      }}
      style={{ padding: '4px 10px', borderRadius: 7, background: '#f5f3ff', color: '#6d28d9', border: '1px solid #ede9fe', fontSize: 10, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
    >
      ✏️ Note
    </button>

    {/* 👇 Cancel button — hide if already completed */}
    {!isCompleted && (
      <CancelActivityButton act={a} onSuccess={onSuccess} />
    )}
  </div>
</td>
                    {/* chevron */}
                    <td style={{ ...tdR, textAlign: 'center', width: 44 }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 8, border: `1px solid ${isExp ? S.brand : S.stone200}`, background: isExp ? S.brand : '#fff', color: isExp ? '#fff' : S.stone400, fontSize: 11, transition: 'all 250ms', transform: isExp ? 'rotate(180deg)' : 'none', boxShadow: isExp ? '0 2px 6px rgba(5,150,105,.3)' : 'none' }}>▾</div>
                    </td>
                  </tr>
 
                  {/* Expanded detail */}
                  {isExp && (
                    <tr>
                      <td colSpan={11} style={{ padding: 0, borderBottom: `1px solid ${S.stone200}`, background: S.stone25 }}>
                        <div style={{ padding: '16px 20px' }}>
                          {/* Stat strip */}
                          <div style={{ display: 'flex', borderRadius: 14, overflow: 'hidden', background: '#fff', marginBottom: 14, boxShadow: S.shadowCard }}>
                            {[{ val: `Job #${a.booking_id ?? '—'} · Act #${a.api_activity_id || '—'}`, lbl: 'Job ID' },
                              { val: `${a.crop_name}${a.variety ? ` (${a.variety})` : ''}`, lbl: 'Crop' },
                              { val: `${a.total_area} ac`,     lbl: 'Plot Area'    },
                              { val: <span style={{ color: S.green700 }}>₹{Math.round(a.total_price).toLocaleString('en-IN')}</span>, lbl: 'Farmer Cost' },
                              { val: a.allocation_status === 'pending' ? <span style={{ color: S.amber600 }}>Pending</span> : isCompleted ? <span style={{ color: S.green600 }}>Completed</span> : <span style={{ color: S.sky600 }}>Allocated</span>, lbl: 'Status' },
                            ].map((s, i) => (
                              <div key={i} style={{ flex: 1, padding: '10px 14px', textAlign: 'center', borderRight: i < 4 ? `1px solid ${S.stone100}` : 'none', position: 'relative' }}>
                                <div style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)', width: 24, height: 2, borderRadius: 1, background: S.green100 }} />
                                <div style={{ fontSize: 14, fontWeight: 800, letterSpacing: '-.3px', lineHeight: 1.3, marginTop: 4 }}>{s.val}</div>
                                <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.7px', color: S.stone400, marginTop: 3 }}>{s.lbl}</div>
                              </div>
                            ))}
                          </div>
 
                          {/* Split info */}
                          {a.is_split && a.splits?.length > 1 && (
                            <div style={{ marginBottom: 12, padding: '10px 14px', background: '#faf5ff', borderRadius: 10, border: '1px solid #e9d5ff' }}>
                              <div style={{ fontSize: 11, fontWeight: 700, color: S.violet700, marginBottom: 6 }}>🔀 Split into {a.splits.length} parts</div>
                              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                {a.splits.map((sp: any, si: number) => (
                                  <div key={si} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 8, background: '#fff', border: '1px solid #e9d5ff', color: S.stone600 }}>
                                    <span style={{ fontWeight: 700, color: S.violet700 }}>Part {si + 1}</span> · {sp.total_area} ac · <span style={{ color: sp.allocation_status === 'pending' ? S.red600 : S.green600 }}>{sp.allocation_status}</span>
                                    {sp.scheduled_date && ` · ${sp.scheduled_date}`} · 👷 {sp.allocation_count}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
 
                          {/* Allocations */}
                          {a.allocation_count === 0 ? (
                            <div style={{ padding: '12px 16px', background: '#fff', borderRadius: 10, border: `1px solid ${S.stone200}`, fontSize: 12, color: S.stone400 }}>
                              <div style={{ fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, marginBottom: 8, paddingBottom: 6, borderBottom: `1px solid ${S.stone100}` }}>⚠ No Allocations Yet</div>
                              <div style={{ background: S.stone50, borderRadius: 8, padding: '8px 12px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' }}>
                                  <span style={{ color: S.stone500 }}>Scheduled</span>
                                  <span style={{ fontWeight: 600 }}>{a.scheduled_date || '—'}</span>
                                </div>
                                {isOverdue && (
                                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0', borderTop: `1px solid ${S.stone100}` }}>
                                    <span style={{ color: S.stone500 }}>Overdue</span>
                                    <span style={{ fontWeight: 600, color: S.red600 }}>{overdueDays} days</span>
                                  </div>
                                )}
                              </div>
                            </div>
                          ) : (
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: S.stone400, marginBottom: 8, paddingBottom: 6, borderBottom: `1px solid ${S.stone100}` }}>📝 Allocation Details</div>
                              {(a.allocations || []).map((alloc: any, ai: number) => {
                                const isDone = alloc.work_status === 'completed';
                                return (
                                  <div key={ai} style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', padding: '10px 14px', marginBottom: 6, borderRadius: 10, background: isDone ? S.green50 : '#fff', border: `1px solid ${isDone ? S.green100 : S.stone200}`, fontSize: 12 }}>
                                    <div style={{ minWidth: 140 }}>
                                      <div style={{ fontWeight: 700, color: S.stone900 }}>👷 {alloc.mukkadam_name}</div>
                                      {alloc.mukkadam_mobile && <div style={{ fontFamily: S.mono, fontSize: 10, color: S.stone400 }}>📞 {alloc.mukkadam_mobile}</div>}
                                    </div>
                                    {alloc.cluster_name && <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: S.sky50, color: S.sky700, border: `1px solid ${S.sky100}` }}>🏘 {alloc.cluster_name}</span>}
                                    <div style={{ color: S.stone600 }}>📅 {alloc.allocated_date || '—'}</div>
                                    <div style={{ color: S.green700 }}>🌾 {alloc.allocated_area} ac{alloc.actual_area_done != null ? ` · ✓ ${alloc.actual_area_done} actual` : ''}</div>
                                    <div style={{ color: S.stone600 }}>👥 {alloc.allocated_workers} workers{alloc.actual_crew_size != null ? ` · ✓ ${alloc.actual_crew_size}` : ''}</div>
                                    <div style={{ color: S.violet600, fontWeight: 600, fontFamily: S.mono, fontSize: 11 }}>₹{alloc.mukkadam_rate}/ac → ₹{Math.round(alloc.mukkadam_est).toLocaleString('en-IN')}</div>
                                    <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, fontWeight: 700, background: isDone ? S.green50 : alloc.work_status === 'in_progress' ? S.sky50 : S.stone100, color: isDone ? S.green700 : alloc.work_status === 'in_progress' ? S.sky700 : S.stone600, border: `1px solid ${isDone ? S.green100 : alloc.work_status === 'in_progress' ? S.sky100 : S.stone200}` }}>{alloc.work_status}</span>
                                    {alloc.report_submitted && <span style={{ fontSize: 11, color: S.sky600 }}>📋 Report</span>}
                                    {alloc.farmer_agreed === true  && <span style={{ fontSize: 11, color: S.green700 }}>✅ Agreed</span>}
                                    {alloc.farmer_agreed === false && <span style={{ fontSize: 11, color: S.red600  }}>❌ Disputed</span>}
                                    {!isDone && isAdmin && (
                                      <button onClick={() => { if (confirm(`Mark ${alloc.mukkadam_name}'s allocation as complete?`)) handleUpdownComplete(alloc.mukkadam_id, alloc.allocation_id); }}
                                        style={{ marginLeft: 'auto', padding: '5px 14px', borderRadius: 8, border: 'none', background: 'linear-gradient(135deg,#059669,#047857)', color: '#fff', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', boxShadow: '0 1px 4px rgba(5,150,105,.25)' }}>
                                        ✅ Mark Complete
                                      </button>
                                    )}
                                    {isDone && <span style={{ marginLeft: 'auto', fontSize: 11, color: S.green700, fontWeight: 700 }}>✅ Done</span>}
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {/* ── Notes for this job ── */}
                          {rowNotes.length > 0 && (
                            <div style={{ marginTop: 12, borderTop: `1px solid ${S.stone100}`, paddingTop: 12 }}>
                              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.7px', color: S.stone400, marginBottom: 8 }}>
                                ✏️ Notes ({rowNotes.length})
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                {rowNotes.map((n: any) => (
                                  <div key={n.id} style={{ padding: '10px 12px', borderRadius: 10, background: n.is_resolved ? '#f0fdf4' : '#fff', border: `1px solid ${n.is_resolved ? '#bbf7d0' : '#fecaca'}`, opacity: n.is_resolved ? 0.75 : 1 }}>
                                    {/* Job context banner */}
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        {n.tags?.map((t: string) => (
                                          <span key={t} style={{ fontSize: 10, padding: '2px 7px', borderRadius: 999, background: '#f3f4f6', color: '#6b7280', fontWeight: 600 }}>{t}</span>
                                        ))}
                                        {n.is_resolved && (
                                          <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 999, background: '#dcfce7', color: '#15803d', fontWeight: 700 }}>✅ Resolved</span>
                                        )}
                                      </div>
                                      <span style={{ fontSize: 10, color: S.stone400, fontFamily: 'monospace' }}>
                                        {n.author?.full_name} · {new Date(n.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                                      </span>
                                    </div>
                                    {/* Note text */}
                                    <div style={{ fontSize: 12, color: n.is_resolved ? '#6b7280' : '#111827', lineHeight: 1.5, textDecoration: n.is_resolved ? 'line-through' : 'none' }}>
                                      {n.text}
                                    </div>
                                    {/* Resolution note */}
                                    {n.resolution_note && (
                                      <div style={{ fontSize: 11, color: '#15803d', fontStyle: 'italic', marginTop: 4 }}>
                                        ✅ {n.resolution_note}
                                        {n.resolved_by?.full_name && ` — ${n.resolved_by.full_name}`}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                              {/* Quick add note button */}
                              <button
                                onClick={() => {
                                  const label = [a.activity_name, a.farmer_name, a.plot_name ? `📍 ${a.plot_name}` : null].filter(Boolean).join(' – ');
                                  onNote(a.job_id, label);
                                }}
                                style={{ marginTop: 8, padding: '5px 12px', borderRadius: 8, background: '#f5f3ff', color: '#6d28d9', border: '1px solid #ede9fe', fontSize: 11, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
                              >
                                + Add another note
                              </button>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}



function CancelActivityButton({ act, onSuccess }: { act: any; onSuccess: () => void }) {
  const [open, setOpen]       = useState(false);
  const [reason, setReason]   = useState('');
  const [cancelAllocs, setCancelAllocs] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const hasActiveAllocs = (act.allocations ?? []).some(
    (al: any) => al.work_status !== 'completed'
  );

  async function handleConfirm() {
    if (!reason.trim()) { setError('Reason is required'); return; }

    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('auth_token')
      const res = await fetch(`${API_BASE_URL}/api/job-activities/${act.activity_id}/cancel/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' ,'Authorization':`Token ${token}`},
        body: JSON.stringify({ reason: reason.trim(), cancel_allocations: cancelAllocs }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to cancel');
      setOpen(false);
      setReason('');
      setCancelAllocs(false);
      onSuccess();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(true)}
        style={{ padding: '4px 10px', borderRadius: 7, background: '#fff1f2', color: '#be123c', border: '1px solid #fecaca', fontSize: 10, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
      >
        🚫 Cancel
      </button>

      {/* Modal */}
      {open && (
        <div
          onClick={() => !loading && setOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{ background: '#fff', borderRadius: 16, padding: 24, width: 420, boxShadow: '0 20px 60px rgba(0,0,0,0.2)', display: 'flex', flexDirection: 'column', gap: 16 }}
          >
            {/* Header */}
            <div>
              <div style={{ fontWeight: 800, fontSize: 16, color: '#be123c' }}>🚫 Cancel Activity</div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                {act.activity_name} · {act.farmer_name} · {act.plot_code}
              </div>
            </div>

            {/* Reason */}
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: '#374151', display: 'block', marginBottom: 6 }}>
                Reason <span style={{ color: '#be123c' }}>*</span>
              </label>
              <textarea
                value={reason}
                onChange={e => { setReason(e.target.value); setError(''); }}
                placeholder="Why is this activity being cancelled?"
                rows={3}
                style={{ width: '100%', borderRadius: 8, border: '1px solid #e5e7eb', padding: '8px 10px', fontSize: 12, fontFamily: 'inherit', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }}
              />
            </div>

            {/* Cancel allocations checkbox — only show if there are active allocs */}
            {hasActiveAllocs && (
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer', padding: '10px 12px', borderRadius: 10, background: cancelAllocs ? '#fff1f2' : '#f9fafb', border: `1px solid ${cancelAllocs ? '#fecaca' : '#e5e7eb'}`, transition: 'all 150ms' }}>
                <input
                  type="checkbox"
                  checked={cancelAllocs}
                  onChange={e => setCancelAllocs(e.target.checked)}
                  style={{ marginTop: 2, accentColor: '#be123c', width: 14, height: 14, flexShrink: 0 }}
                />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#374151' }}>Also cancel linked allocations</div>
                  <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
                    {(act.allocations ?? []).filter((al: any) => al.work_status !== 'completed').length} active allocation(s) will be cancelled.
                    Completed ones will be kept.
                  </div>
                </div>
              </label>
            )}

            {/* Error */}
            {error && (
              <div style={{ fontSize: 11, color: '#be123c', padding: '8px 12px', background: '#fff1f2', borderRadius: 8, border: '1px solid #fecaca' }}>
                ⚠ {error}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => { setOpen(false); setReason(''); setError(''); setCancelAllocs(false); }}
                disabled={loading}
                style={{ padding: '7px 16px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', color: '#374151' }}
              >
                Keep
              </button>
              <button
                onClick={handleConfirm}
                disabled={loading || !reason.trim()}
                style={{ padding: '7px 16px', borderRadius: 8, border: 'none', background: loading || !reason.trim() ? '#fca5a5' : '#be123c', color: '#fff', fontSize: 12, fontWeight: 700, cursor: loading || !reason.trim() ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}
              >
                {loading ? 'Cancelling…' : 'Confirm Cancel'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
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




export function MukkadamPayout() {
  // ── state ─────────────────────────────────────────────────────────────────
  const [overviewData, setOverviewData]   = useState<any>(null);
  const [allMukkadams, setAllMukkadams]   = useState<any[]>([]);
  const [loading, setLoading]             = useState(true);
  const [expanded, setExpanded]           = useState<number | null>(null);
  const [activeTab, setActiveTab]         = useState<Record<number, string>>({});
  const [showAddEntry, setShowAddEntry]   = useState<number | null>(null);
  const [adhocForm, setAdhocForm]         = useState<Record<string, any>>({});  // keyed by mukkadam_id
  const [adhocSaving, setAdhocSaving]     = useState<number | null>(null);
  const [payModal, setPayModal]           = useState<any>(null);
  const [settlPayModal, setSettlPayModal] = useState<any>(null);  // { mukkadam, jobId, amount, farmerName }
  const [filter, setFilter]               = useState<string>('all');

  const getTab = (id: number) => activeTab[id] || 'timeline';
  const setTab = (id: number, t: string) => setActiveTab(p => ({ ...p, [id]: t }));

  const fmt  = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`;
  const fmtK = (n: number) => n >= 100000 ? `₹${(n/100000).toFixed(1)}L` : n >= 1000 ? `₹${(n/1000).toFixed(1)}k` : `₹${n}`;

  // ── fetch overview → then fetch every cluster detail in parallel ──────────
  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    fetch(`${API_BASE_URL}/api/mukkadam-payment-overview/`, {
      headers: { Authorization: `Token ${token}` },
    })
      .then(r => r.json())
      .then(async (overview) => {
        setOverviewData(overview);
        const clusters: any[] = overview.cluster_billing ?? [];
        if (clusters.length === 0) { setLoading(false); return; }
        // fetch all cluster details in parallel
        const details = await Promise.all(
          clusters.map((c: any) =>
            fetch(`${API_BASE_URL}/api/cluster/${c.cluster_id}/payment-dashboard/`, {
              headers: { Authorization: `Token ${token}` },
            }).then(r => r.json()).catch(() => null)
          )
        );
        // flatten mukkadams from all clusters, merge duplicates by mukkadam_id
        const mergeMap = new Map<number, any>();
        details.forEach((d: any, i: number) => {
          if (!d) return;
          (d.mukkadams ?? []).forEach((m: any) => {
            const id = m.mukkadam_id;
            if (!mergeMap.has(id)) {
              mergeMap.set(id, {
                ...m,
                _cluster_name: clusters[i].cluster_name,
                _cluster_id:   clusters[i].cluster_id,
                _clusters: [{ id: clusters[i].cluster_id, name: clusters[i].cluster_name }],
                _clusterTypes: { [clusters[i].cluster_id]: m.mukkadam_type },
              });
            } else {
              // same mukkadam in another cluster — merge arrays, keep first cluster as primary
              const existing = mergeMap.get(id)!;
              existing._clusters.push({ id: clusters[i].cluster_id, name: clusters[i].cluster_name });
              existing._clusterTypes = { ...(existing._clusterTypes ?? {}), [clusters[i].cluster_id]: m.mukkadam_type };
              // merge settlements (by job_id to avoid duplicates)
              const existingJobIds = new Set((existing.settlements ?? []).map((s: any) => s.job_id));
              (m.settlements ?? []).forEach((s: any) => {
                if (!existingJobIds.has(s.job_id)) existing.settlements = [...(existing.settlements ?? []), s];
              });
              // merge updown_allocations (by allocation_id)
              const existingAllocIds = new Set((existing.updown_allocations ?? []).map((a: any) => a.allocation_id));
              (m.updown_allocations ?? []).forEach((a: any) => {
                if (!existingAllocIds.has(a.allocation_id)) existing.updown_allocations = [...(existing.updown_allocations ?? []), a];
              });
              // merge transaction_history (by id/date+type to avoid dups)
              const existingTxnKeys = new Set((existing.transaction_history ?? []).map((t: any) => `${t.type}-${t.date}-${t.amount}`));
              (m.transaction_history ?? []).forEach((t: any) => {
                const key = `${t.type}-${t.date}-${t.amount}`;
                if (!existingTxnKeys.has(key)) existing.transaction_history = [...(existing.transaction_history ?? []), t];
              });
              // merge missed_weekly_dates
              const existingMissed = new Set(existing.missed_weekly_dates ?? []);
              (m.missed_weekly_dates ?? []).forEach((d2: string) => existingMissed.add(d2));
              existing.missed_weekly_dates = Array.from(existingMissed).sort();
              // sum totals
              existing.total_weekly_paid  = (existing.total_weekly_paid  ?? 0) + (m.total_weekly_paid  ?? 0);
              existing.advance_amount     = Math.max(existing.advance_amount ?? 0, m.advance_amount ?? 0);
            }
          });
        });
        setAllMukkadams(Array.from(mergeMap.values()));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // ── reload a single cluster after a payment ───────────────────────────────
  const reloadCluster = async (clusterId: number) => {
    const token = localStorage.getItem('auth_token');
    const d = await fetch(`${API_BASE_URL}/api/cluster/${clusterId}/payment-dashboard/`, {
      headers: { Authorization: `Token ${token}` },
    }).then(r => r.json()).catch(() => null);
    if (!d) return;
    setAllMukkadams(prev => {
      const clusterName = prev.find((x: any) => x._clusters?.some((c: any) => c.id === clusterId))?._clusters?.find((c: any) => c.id === clusterId)?.name
                       ?? prev.find((x: any) => x._cluster_id === clusterId)?._cluster_name ?? '';
      // Remove this cluster's contribution from all merged mukkadams
      // Simplest: remove mukkadams that were primarily from this cluster,
      // then re-add fresh. For mukkadams in multiple clusters, keep their other-cluster data.
      const fresh = new Map<number, any>();
      // keep all existing mukkadams that are NOT primarily from this cluster
      prev.forEach((m: any) => {
        const clusters = m._clusters ?? [{ id: m._cluster_id, name: m._cluster_name }];
        const otherClusters = clusters.filter((c: any) => c.id !== clusterId);
        if (otherClusters.length > 0) {
          // mukkadam has other clusters — keep but strip this cluster's settlements/allocs
          // (we'll re-add them below from fresh data)
          const otherTypes: Record<number, string> = {};
          otherClusters.forEach((c: any) => { if (m._clusterTypes?.[c.id]) otherTypes[c.id] = m._clusterTypes[c.id]; });
          fresh.set(m.mukkadam_id, { ...m, _clusters: otherClusters, _clusterTypes: otherTypes });
        }
        // if only in this cluster, drop — will be re-added below
      });
      // merge in fresh data from reloaded cluster
      (d.mukkadams ?? []).forEach((m: any) => {
        const id = m.mukkadam_id;
        if (!fresh.has(id)) {
          fresh.set(id, { ...m, _cluster_name: clusterName, _cluster_id: clusterId, _clusters: [{ id: clusterId, name: clusterName }], _clusterTypes: { [clusterId]: m.mukkadam_type } });
        } else {
          const existing = fresh.get(id)!;
          existing._clusters = [...(existing._clusters ?? []), { id: clusterId, name: clusterName }];
          existing._clusterTypes = { ...(existing._clusterTypes ?? {}), [clusterId]: m.mukkadam_type };
          const existingJobIds = new Set((existing.settlements ?? []).map((s: any) => s.job_id));
          (m.settlements ?? []).forEach((s: any) => { if (!existingJobIds.has(s.job_id)) existing.settlements = [...(existing.settlements ?? []), s]; });
          const existingAllocIds = new Set((existing.updown_allocations ?? []).map((a: any) => a.allocation_id));
          (m.updown_allocations ?? []).forEach((a: any) => { if (!existingAllocIds.has(a.allocation_id)) existing.updown_allocations = [...(existing.updown_allocations ?? []), a]; });
        }
      });
      return Array.from(fresh.values());
    });
  };

  // ── helpers ───────────────────────────────────────────────────────────────
  const Chip = ({ status }: { status: string }) => {
    const cfg: Record<string, any> = {
      paid:                 { bg: '#f0fdf4', color: '#16a34a', border: '#bbf7d0', label: '✓ Paid'    },
      due:                  { bg: '#fefce8', color: '#ca8a04', border: '#fde68a', label: '⏳ Due'     },
      pending_verification: { bg: '#fff7ed', color: '#ea580c', border: '#fed7aa', label: '⏳ Pending' },
      na:                   { bg: '#f5f5f4', color: '#a3a398', border: '#e8e5de', label: 'N/A'       },
    };
    const s = cfg[status] ?? cfg.na;
    return <span style={{ display: 'inline-flex', padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>{s.label}</span>;
  };

  const ModeBadge = ({ type }: { type: string }) => {
    const cfg: Record<string, any> = {
      permanent: { bg: '#f0fdf4', color: '#16a34a', border: '#bbf7d0', label: '📋 Settlement Schedule' },
      updown:    { bg: '#fff7ed', color: '#ea580c', border: '#fed7aa', label: '🔄 Up-Down' },
      mixed:     { bg: '#f5f3ff', color: '#7c3aed', border: '#ddd6fe', label: '📋 Settlement Schedule (Mixed)' },
    };
    const s = cfg[type] ?? { bg: '#f5f4ef', color: '#a3a398', border: '#e8e5de', label: type };
    return <span style={{ padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 700, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>{s.label}</span>;
  };

  const CreatedByTag = ({ name }: { name: string | null }) => name ? (
    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#eff6ff', color: '#2563eb', fontWeight: 600, border: '1px solid #bfdbfe' }}>✏️ {name}</span>
  ) : null;

  const VerifiedByTag = ({ name }: { name: string | null }) => name ? (
    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#f0fdf4', color: '#16a34a', fontWeight: 600, border: '1px solid #bbf7d0' }}>✓ {name}</span>
  ) : (
    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#fff7ed', color: '#ea580c', fontWeight: 600, border: '1px solid #fed7aa' }}>⏳ Awaiting admin</span>
  );

  const Bar = ({ pct }: { pct: number }) => {
    const color = pct > 60 ? '#16a34a' : pct > 25 ? '#ea580c' : '#dc2626';
    return (
      <div style={{ background: '#f0ede7', borderRadius: 4, height: 4, width: '100%', overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', borderRadius: 4, background: color, transition: 'width 0.4s' }} />
      </div>
    );
  };

  // ── loading ───────────────────────────────────────────────────────────────
  if (loading || !overviewData) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '64px 0' }}>
      <RefreshCw size={28} style={{ color: '#7c3aed', animation: 'spin 1s linear infinite' }} />
    </div>
  );

  const pipe    = overviewData.pipeline ?? {};
  const vQueue  = overviewData.verification_queue ?? [];
  const recent  = overviewData.recent_payments ?? [];

  // ── derive per-mukkadam summary values ────────────────────────────────────
  const enriched = allMukkadams.map((m: any) => {
    const txns: any[]    = m.transaction_history ?? [];
    const advancePaid    = Math.abs(txns.filter((t: any) => t.type === 'advance').reduce((s: number, t: any) => s + t.amount, 0));
    const weeklyPaid     = m.total_weekly_paid ?? 0;
    const settlePaid     = (m.settlements ?? []).filter((s: any) => s.status === 'paid').reduce((sum: number, s: any) => sum + s.net_payable, 0);
    const structuredPaid = advancePaid + weeklyPaid + settlePaid + (m.transport_price ?? 0);
    const miscCosts      = (m.settlements ?? []).flatMap((s: any) => s.misc_costs ?? []);
    const adhocTot       = miscCosts.reduce((sum: number, c: any) => sum + c.amount, 0);
    const totalOut       = structuredPaid + adhocTot;
    const settlesPending = (m.settlements ?? []).filter((s: any) => s.status === 'calculated' && s.net_payable > 0);
                       // permanent: no daily
    const initials       = m.mukkadam_name.split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase();
    const paidCount      = txns.filter((t: any) => t.amount !== 0).length;
    const isUpdown       = m.mukkadam_type === 'updown';
    const missedCount    = isUpdown ? 0 : (m.missed_weekly_dates?.length ?? 0);  // updown has no weekly
    const hasAction      = settlesPending.length > 0 || missedCount > 0;
    const allAllocs: any[] = (m.settlements ?? []).flatMap((s: any) => s.activities ?? []);
    // permanent: area from settlement activities; updown: area from updown_allocations
    const updownAllocs: any[] = m.updown_allocations ?? [];
    const totalAcres     = isUpdown
      ? updownAllocs.reduce((sum: number, a: any) => sum + (a.allocated_area || 0), 0)
      : allAllocs.reduce((sum: number, a: any) => sum + (a.allocated_area || 0), 0);
    const completedAcres = isUpdown
      ? updownAllocs.filter((a: any) => a.work_status === 'completed').reduce((sum: number, a: any) => sum + (a.actual_area_done ?? a.allocated_area ?? 0), 0)
      : allAllocs.filter((a: any) => a.work_status === 'completed').reduce((sum: number, a: any) => sum + (a.allocated_area || 0), 0);
    const acrePct        = totalAcres > 0 ? (completedAcres / totalAcres) * 100 : 0;
    // work status label for updown
    const updownDoneCount  = updownAllocs.filter((a: any) => a.work_status === 'completed').length;
    const updownTotalCount = updownAllocs.length;
    // permanent: count activities assigned vs completed
    const permTotalActs    = allAllocs.length;
    const permDoneActs     = allAllocs.filter((a: any) => a.work_status === 'completed').length;
    // column values
     const weeklyPayAmt_m     = m.weekly_payment_amount    ?? m.assignment?.weekly_payment_amount;
    const scheduledVal   = isUpdown
      ? (m.settlements ?? []).reduce((acc: number, st: any) => acc + Number(st.transport_deducted || 0), 0)  // total transport earned
      : (weeklyPayAmt_m ?? 0);    // permanent: weekly rate
    const dailyVal       = isUpdown
      ? (m.transport_price ?? 0) // transport per allocation (daily rate)
      : 0;     
    const isPermanent    = m.mukkadam_type === 'permanent';
    // mixed type detection — mukkadam assigned as permanent in one cluster, updown in another
    const clusterTypeMap: Record<number, string> = m._clusterTypes ?? {};
    const clusterTypeVals = Object.values(clusterTypeMap);
    const isMixed        = clusterTypeVals.includes('permanent') && clusterTypeVals.includes('updown');
    const permanentClusters_m = (m._clusters ?? []).filter((c: any) => (clusterTypeMap[c.id] ?? 'permanent') === 'permanent');
    const updownClusters_m    = (m._clusters ?? []).filter((c: any) => (clusterTypeMap[c.id] ?? '') === 'updown');
    // has any payment activity
    const hasPayment     = totalOut > 0 || hasAction || missedCount > 0 || settlesPending.length > 0;

    // ── updown vs permanent helpers (from Farm.tsx) ──────────────────────────
    const assignmentId_m     = m.assignment_id ?? m.assignment?.assignment_id;
    const weeklyPayDayVal_m  = m.weekly_payment_day_value ?? m.assignment?.weekly_payment_day_value;
   
    const weeklyPayDayLbl_m  = m.weekly_payment_day_label ?? m.assignment?.weekly_payment_day_label;
    const alreadyPaidToday_m = m.already_paid_today       ?? m.assignment?.already_paid_today;
    const missedWeeklyDates_m: string[] = Array.isArray(m.missed_weekly_dates) ? m.missed_weekly_dates : [];
    const todayJs_m = new Date().getDay();
    const todayPy_m = todayJs_m === 0 ? 6 : todayJs_m - 1;
    const weeklyDueToday_m = !isUpdown && weeklyPayDayVal_m === todayPy_m && !alreadyPaidToday_m;

    const isShootSelectionDone_m = (st: any) => {
      const acts = st.activities || [];
      return acts.some((a: any) => {
        const name = (a.activity_name || '').toLowerCase();
        return ((name.includes('shoot') && name.includes('select')) ||
               (a.activity_name || '').includes('\u0935\u093f\u0930\u0933\u0923\u0940')) &&
               a.work_status === 'completed';
      });
    };

    const jobsReadyToPay_m = isUpdown
      ? (m.settlements ?? []).filter((st: any) => st.status === 'calculated' && Number(st.net_payable) > 0.01)
      : (m.settlements ?? []).filter((st: any) => st.status === 'calculated' && Number(st.net_payable) > 0.01 && isShootSelectionDone_m(st));

    const netPayableOverall_m = jobsReadyToPay_m.reduce((acc: number, st: any) => acc + Number(st.net_payable || 0), 0);

    return { ...m, advancePaid, weeklyPaid, settlePaid, structuredPaid, miscCosts, adhocTot, totalOut, settlesPending, missedCount, hasAction, allAllocs, totalAcres, completedAcres, acrePct, initials, paidCount, isUpdown, isPermanent, hasPayment,
             assignmentId_m, weeklyPayDayVal_m, weeklyPayAmt_m, weeklyPayDayLbl_m, alreadyPaidToday_m, missedWeeklyDates_m, weeklyDueToday_m, isShootSelectionDone_m, jobsReadyToPay_m, netPayableOverall_m,
             updownAllocs, updownDoneCount, updownTotalCount, permTotalActs, permDoneActs, scheduledVal, dailyVal,
             isMixed, permanentClusters_m, updownClusters_m };
  });

  // ── filter ────────────────────────────────────────────────────────────────
  const filtered = enriched.filter((m: any) => {
    if (filter === 'all')           return m.hasPayment || m.totalOut > 0;
    if (filter === 'weekly_due')    return !m.isUpdown && ((m.missed_weekly_dates?.length ?? 0) > 0 || m.weeklyDueToday_m);
    if (filter === 'settlement')    return m.settlesPending.length > 0;
    if (filter === 'action')        return m.hasAction;
    return true;
  });

  // ── overview numbers ──────────────────────────────────────────────────────
  const totalPaidOut    = pipe.total_paid_out?.amount ?? 0;
  // Compute weekly due count from enriched (API count is unreliable after merge)
  const weeklyDueCount  = enriched.filter((m: any) => !m.isUpdown && (m.missedCount > 0 || m.weeklyDueToday_m)).length;
  const weeklyDueAmt    = enriched.filter((m: any) => !m.isUpdown && (m.missedCount > 0 || m.weeklyDueToday_m)).reduce((acc: number, m: any) => acc + ((m.missedCount + (m.weeklyDueToday_m ? 1 : 0)) * (m.weeklyPayAmt_m ?? 0)), 0);
  const settlePendCount = pipe.settlement_pending?.count ?? 0;
  const settlePendAmt   = pipe.settlement_pending?.amount ?? 0;
  const activeCount     = pipe.mukkadams_active?.count ?? 0;

  return (
    <div>
      {/* ── Pipeline KPI cards ── */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>MUKKADAM PAYOUT PIPELINE</div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {[
            { icon: '📅', label: 'Weekly Due',        val: weeklyDueCount,  amount: weeklyDueAmt,   color: '#ca8a04', bg: '#fefce8', border: '#fde68a',  sub: 'Mukkadams to pay today', onClick: () => setFilter('weekly_due') },
            { icon: '💰', label: 'Settlement Pending', val: settlePendCount, amount: settlePendAmt,  color: '#dc2626', bg: '#fef2f2', border: '#fecaca',  sub: 'Acre settlements due',    onClick: () => setFilter('settlement') },
            { icon: '✅', label: 'Total Paid Out',     val: fmtK(totalPaidOut), amount: 0, noCount: true, color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', sub: 'All time' },
            { icon: '👷', label: 'Active Mukkadams',  val: activeCount,     amount: 0,              color: '#7c3aed', bg: '#f5f3ff', border: '#ddd6fe',  sub: 'Across all clusters' },
          ].map((card: any, i: number) => (
            <div key={i} onClick={card.onClick} style={{ flex: 1, minWidth: 140, background: card.bg, borderRadius: 12, border: `1.5px solid ${card.border}`, padding: '14px 16px', textAlign: 'center', cursor: card.onClick ? 'pointer' : 'default' }}>
              <div style={{ fontSize: 11, color: card.color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>{card.icon} {card.label}</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: card.color, lineHeight: 1.1 }}>{card.val}</div>
              {!card.noCount && card.amount > 0 && <div style={{ fontSize: 14, fontWeight: 700, color: card.color, marginTop: 2 }}>{fmt(card.amount)}</div>}
              <div style={{ fontSize: 11, color: '#a3a398', marginTop: 3 }}>{card.sub}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Verification Queue ── */}
      {vQueue.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 15 }}>🔐</span>
            <span style={{ fontSize: 14, fontWeight: 700 }}>Payment Admin — Verification Queue</span>
            <span style={{ padding: '2px 10px', borderRadius: 10, fontSize: 12, fontWeight: 700, background: '#fff7ed', color: '#ea580c', border: '1px solid #fed7aa' }}>{vQueue.length} pending</span>
            <span style={{ fontSize: 12, color: '#6b6b63' }}>— Weekly payments don't need verification. All others do.</span>
          </div>
          <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #fed7aa', overflow: 'hidden' }}>
            {vQueue.map((q: any, i: number) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', borderBottom: i < vQueue.length - 1 ? '1px solid #f0ede7' : 'none', background: q.urgency === 'high' ? 'rgba(254,243,199,0.2)' : 'transparent' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: q.urgency === 'high' ? '#dc2626' : q.urgency === 'medium' ? '#ea580c' : '#ca8a04' }} />
                <div style={{ fontWeight: 600, minWidth: 160, fontSize: 13 }}>{q.mukkadam_name}</div>
                <span style={{ padding: '2px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: '#f5f3ff', color: '#7c3aed', border: '1px solid #ddd6fe' }}>{q.reason ?? q.label}</span>
                {q.created_by && <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#eff6ff', color: '#2563eb', fontWeight: 600, border: '1px solid #bfdbfe' }}>✏️ {q.created_by}</span>}
                <div style={{ flex: 1 }} />
                <div style={{ fontSize: 15, fontWeight: 700 }}>{fmt(q.amount)}</div>
                <button onClick={async () => {
                  const token = localStorage.getItem('auth_token');
                  await fetch(`${API_BASE_URL}/api/mukkadam-misc-cost/${q.cost_id}/verify/`, { method: 'POST', headers: { Authorization: `Token ${token}` } });
                  // reload overview
                  const res = await fetch(`${API_BASE_URL}/api/mukkadam-payment-overview/`, { headers: { Authorization: `Token ${token}` } });
                  setOverviewData(await res.json());
                }} style={{ padding: '6px 14px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>✓ Verify & Pay</button>
                <button style={{ padding: '6px 8px', borderRadius: 6, border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' }}>✗</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Filter pills ── */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
        {[
          { key: 'all',        label: `All ${enriched.filter((m:any) => m.hasPayment || m.totalOut > 0).length}` },
          { key: 'weekly_due', label: '📅 Weekly Due',       color: '#ca8a04' },
          { key: 'settlement', label: '💰 Settlement Pending', color: '#dc2626' },
          { key: 'action',     label: '⏳ Needs Action',     color: '#ea580c' },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)} style={{
            padding: '5px 14px', borderRadius: 20, cursor: 'pointer', fontSize: 12, fontWeight: 600,
            border: `1px solid ${filter === f.key ? ((f as any).color || '#059669') : '#e8e5de'}`,
            background: filter === f.key ? (((f as any).color || '#059669') + '14') : '#fff',
            color: filter === f.key ? ((f as any).color || '#059669') : '#6b6b63',
            fontFamily: 'inherit',
          }}>{f.label}</button>
        ))}
      </div>

      {/* ── Mukkadam cards (flat, no cluster grouping) ── */}
      {filtered.length === 0 && (
        <div style={{ padding: '48px 0', textAlign: 'center', color: '#a3a398', fontSize: 13 }}>No mukkadams match this filter.</div>
      )}

      {filtered.map((m: any) => {
        const isExp      = expanded === m.mukkadam_id;
        const currentTab = getTab(m.mukkadam_id);

        return (
          <div key={m.mukkadam_id} id={`mp-${m.mukkadam_id}`} style={{ background: '#fff', borderRadius: 12, border: `1px solid ${m.hasAction ? '#fed7aa' : '#e8e5de'}`, marginBottom: 10, overflow: 'hidden' }}>

            {/* ── CARD HEADER ── */}
            <div
              onClick={() => setExpanded(isExp ? null : m.mukkadam_id)}
              style={{ padding: '12px 16px', cursor: 'pointer', display: 'grid', gridTemplateColumns: '2.5fr 120px 90px 90px 90px 90px 30px', alignItems: 'center', gap: 8 }}
              onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = '#fafaf8'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
            >
              {/* Name + badges */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 38, height: 38, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, background: m.isUpdown ? '#fff7ed' : '#f0fdf4', border: `2px solid ${m.isUpdown ? '#fed7aa' : '#bbf7d0'}`, color: m.isUpdown ? '#ea580c' : '#16a34a' }}>
                  {m.initials}
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 14, fontWeight: 700 }}>{m.mukkadam_name}</span>
                    <ModeBadge type={m.isMixed ? 'mixed' : m.mukkadam_type} />
                    {m.settlesPending.length > 0 && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: '#fff7ed', color: '#ea580c', fontWeight: 700 }}>⏳ Verify</span>}
                    {m.miscCosts.length > 0 && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: '#f5f3ff', color: '#7c3aed', fontWeight: 700 }}>📝 {m.miscCosts.length}</span>}
                    <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: '#eff6ff', color: '#2563eb', fontWeight: 700, border: '1px solid #bfdbfe' }}>📒 {m.paidCount} payments</span>
                    {!m.isUpdown && m.weeklyDueToday_m && <span style={{ fontSize: 9, padding: '1px 7px', borderRadius: 4, background: '#fef9c3', color: '#b45309', fontWeight: 700, border: '1px solid #fde68a' }}>📅 Weekly Due</span>}
                    {m.jobsReadyToPay_m.length > 0 && <span style={{ fontSize: 9, padding: '1px 7px', borderRadius: 4, background: '#fef2f2', color: '#dc2626', fontWeight: 700, border: '1px solid #fecaca' }}>🏦 ₹{Math.round(m.netPayableOverall_m).toLocaleString('en-IN')} due</span>}
                  </div>
                  <div style={{ fontSize: 11, color: '#a3a398', marginTop: 1 }}>
                    {m.crew_size} crew · {(m._clusters ?? [{ name: m._cluster_name }]).map((c: any) => c.name).join(', ')}
                    {!m.isUpdown && m.missedCount > 0 && <span style={{ color: '#dc2626', fontWeight: 600 }}> · ⚠️ {m.missedCount} missed weekly</span>}
                  </div>
                </div>
              </div>

              {/* Work bar */}
              <div style={{ minWidth: 130 }}>
                <div style={{ fontSize: 10, color: '#a3a398', marginBottom: 3 }}>Work</div>
                <Bar pct={m.acrePct} />
                {m.isUpdown ? (
                  <div style={{ fontSize: 10, color: '#6b6b63', marginTop: 2 }}>
                    {m.updownDoneCount}/{m.updownTotalCount} allocs · {m.completedAcres.toFixed(1)}ac
                  </div>
                ) : (
                  <div style={{ fontSize: 10, color: '#6b6b63', marginTop: 2 }}>
                    {m.permDoneActs}/{m.permTotalActs} done · {m.completedAcres.toFixed(1)}/{m.totalAcres.toFixed(1)} ac
                  </div>
                )}
              </div>

              {/* Scheduled — permanent: weekly rate (₹/week); updown: total transport earned */}
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 10, color: '#a3a398' }}>Scheduled</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: m.scheduledVal > 0 ? (m.isPermanent ? '#16a34a' : '#0369a1') : '#a3a398' }}>
                  {m.scheduledVal > 0 ? fmtK(m.scheduledVal) : '—'}
                </div>
              </div>

              {/* Daily — updown: transport_price per alloc; permanent: — */}
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 10, color: '#a3a398' }}>Daily</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: m.isUpdown && m.dailyVal > 0 ? '#ea580c' : '#a3a398' }}>
                  {m.isUpdown && m.dailyVal > 0 ? fmtK(m.dailyVal) : '—'}
                </div>
              </div>

              <div style={{ textAlign: 'right' }}><div style={{ fontSize: 10, color: '#a3a398' }}>Ad-hoc</div><div style={{ fontSize: 14, fontWeight: 700, color: m.adhocTot > 0 ? '#7c3aed' : '#a3a398' }}>{m.adhocTot > 0 ? fmtK(m.adhocTot) : '—'}</div></div>
              <div style={{ textAlign: 'right' }}><div style={{ fontSize: 10, color: '#a3a398' }}>Total Out</div><div style={{ fontSize: 14, fontWeight: 800 }}>{fmtK(m.totalOut)}</div></div>
              <div style={{ textAlign: 'center', color: '#a3a398', fontSize: 13 }}>{isExp ? '▲' : '▼'}</div>
            </div>

            {/* ── EXPANDED DETAIL ── */}
            {isExp && (
              <div style={{ borderTop: '1px solid #f0ede7' }}>
                {/* mode note */}
                <div style={{ padding: '8px 16px', background: '#fafaf8', borderBottom: '1px solid #f0ede7', fontSize: 12, color: '#6b6b63', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ModeBadge type={m.isMixed ? 'mixed' : m.mukkadam_type} />
                  <span>{m.isMixed ? 'Mixed — permanent + up-down contracts across different clusters.' : m.isPermanent ? 'Settlement schedule throughout.' : 'Up-Down — transport costs apply per allocation.'}</span>
                </div>

                {/* Tabs */}
                <div style={{ display: 'flex', borderBottom: '1px solid #e8e5de' }}>
                  {[
                    { key: 'timeline', label: '📋 Payments' },
                    { key: 'adhoc',    label: `📝 Manual Entries (${m.miscCosts.length})` },
                    { key: 'recon',    label: '🔍 Reconciliation' },
                  ].map(t => (
                    <button key={t.key} onClick={() => setTab(m.mukkadam_id, t.key)} style={{ padding: '10px 16px', border: 'none', cursor: 'pointer', background: 'transparent', fontSize: 12, fontWeight: 600, fontFamily: 'inherit', color: currentTab === t.key ? '#2563eb' : '#a3a398', borderBottom: currentTab === t.key ? '2px solid #2563eb' : '2px solid transparent' }}>
                      {t.label}
                    </button>
                  ))}
                </div>

                {/* ── TAB: PAYMENTS ── */}
                {currentTab === 'timeline' && (
                  <div style={{ padding: '14px 16px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>

                      {/* LEFT: One-time + Settlements */}
                      <div>
                        <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', marginBottom: 8 }}>One-Time Payments</div>
                        <div style={{ background: '#fafaf8', borderRadius: 10, border: '1px solid #f0ede7', overflow: 'hidden' }}>
                          {m.advance_amount > 0 && (
                            <div style={{ padding: '10px 12px', borderBottom: '1px solid #f0ede7' }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <div>
                                  <div style={{ fontSize: 13, fontWeight: 600 }}>Advance Payment</div>
                                  <div style={{ marginTop: 3 }}><VerifiedByTag name="Paid" /></div>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(m.advance_amount)}</span>
                                  <Chip status="paid" />
                                </div>
                              </div>
                            </div>
                          )}
                          {m.advance_amount === 0 && (
                            <div style={{ padding: 16, textAlign: 'center', color: '#a3a398', fontSize: 12 }}>No one-time payments yet</div>
                          )}
                        </div>

                        {/* Acre Settlements */}
                        {(m.settlements ?? []).length > 0 && (
                          <div style={{ marginTop: 14 }}>
                            <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', marginBottom: 8 }}>Acre Settlements</div>
                            {(m.settlements ?? []).map((s: any, si: number) => {
                              const sc: Record<string, any> = { paid: { bg: '#f0fdf4', border: '#bbf7d0' }, calculated: { bg: '#fff7ed', border: '#fed7aa' }, pending: { bg: '#fefce8', border: '#fde68a' }, no_payment_needed: { bg: '#f0fdf4', border: '#bbf7d0' } };
                              const c = sc[s.status] ?? sc.pending;
                              return (
                                <div key={si} style={{ background: c.bg, borderRadius: 10, padding: 14, border: `1px solid ${c.border}`, marginBottom: 8, fontSize: 12 }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                                    <div style={{ fontWeight: 700, fontSize: 13 }}>{s.farmer_name}</div>
                                    <Chip status={s.status} />
                                  </div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>Gross</span><span style={{ fontWeight: 600 }}>{fmt(s.gross_amount)}</span></div>
                                  {/* updown: no 10% deposit, transport is ADDED to gross per settlement */}
                                  {m.isUpdown && Number(s.transport_deducted || 0) > 0 && (
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>🚛 + Transport</span><span style={{ color: '#0369a1', fontWeight: 600 }}>+{fmt(s.transport_deducted)}</span></div>
                                  )}
                                  {/* permanent only: 10% deposit holdback */}
                                  {!m.isUpdown && (() => {
                                    const acts = s.activities || [];
                                    const allDone = acts.length > 0 && acts.every((a: any) => a.work_status === 'completed');
                                    return (
                                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                                        <span style={{ color: '#6b6b63' }}>{allDone ? '+ 10% Released ✓' : '− 10% Deposit held'}</span>
                                        <span style={{ color: allDone ? '#16a34a' : '#b45309', fontWeight: 600 }}>{allDone ? '+' : '−'}{fmt(s.deposit_held)}</span>
                                      </div>
                                    );
                                  })()}
                                  {!m.isUpdown && Number(s.payable_90pct || 0) > 0 && (
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>= 90% payable</span><span style={{ fontWeight: 600, color: '#1f2937' }}>{fmt(s.payable_90pct)}</span></div>
                                  )}
                                  {s.deposit_carried_forward > 0 && <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>+ Deposit from prev job</span><span style={{ color: '#0f766e', fontWeight: 600 }}>+{fmt(s.deposit_carried_forward)}</span></div>}
                                  {s.credit_carried_forward > 0 && <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>− Credit to next job</span><span style={{ color: '#6b7280' }}>−{fmt(s.credit_carried_forward)}</span></div>}
                                  {s.advance_deducted > 0 && <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>− Advance (this job)</span><span style={{ color: '#dc2626' }}>−{fmt(s.advance_deducted)}</span></div>}
                                  {s.weekly_payments_deducted > 0 && <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>− Weekly payments</span><span style={{ color: '#dc2626' }}>−{fmt(s.weekly_payments_deducted)}</span></div>}
                                  {Number(s.total_misc || 0) > 0 && <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>− Misc costs</span><span style={{ color: '#dc2626' }}>−{fmt(s.total_misc)}</span></div>}
                                  <div style={{ borderTop: `1px solid ${c.border}`, paddingTop: 6, marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
                                    <span style={{ fontWeight: 700 }}>Net Payable</span>
                                    <span style={{ fontWeight: 800, fontSize: 16, color: '#ea580c' }}>{fmt(s.net_payable)}</span>
                                  </div>
                                  {s.status === 'calculated' && s.net_payable > 0 && (() => {
                                    const shootOk = m.isUpdown || m.isShootSelectionDone_m(s);
                                    return shootOk ? (
                                      <button
                                        onClick={e => { e.stopPropagation(); setSettlPayModal({ mukkadam: m, jobId: s.job_id, amount: s.net_payable, farmerName: s.farmer_name }); }}
                                        style={{ marginTop: 10, width: '100%', padding: '10px', borderRadius: 10, border: 'none', background: '#14b8a6', color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>
                                        🏦 Pay ₹{fmt(s.net_payable)} to {m.mukkadam_name}
                                      </button>
                                    ) : (
                                      <div style={{ marginTop: 8, fontSize: 11, color: '#b45309', background: '#fef9c3', borderRadius: 6, padding: '6px 10px', border: '1px solid #fde68a' }}>
                                        ⚠️ Shoot selection not yet completed — payment locked until then
                                      </div>
                                    );
                                  })()}
                                  {s.status === 'pending' && <div style={{ marginTop: 8, fontSize: 11, color: '#a3a398', textAlign: 'center' }}>Settlement triggers after all activities complete</div>}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      {/* RIGHT: Weekly (permanent only) OR Allocations (updown only) OR BOTH (mixed) */}
                      <div>
                        {m.isMixed ? (
                          /* ── MIXED: both sections labeled by cluster ── */
                          <div>
                            {m.updownClusters_m.map((uc: any) => (
                              <div key={uc.id} style={{ marginBottom: 16 }}>
                                <div style={{ fontSize: 10, fontWeight: 700, color: '#ea580c', textTransform: 'uppercase', marginBottom: 6 }}>🔄 Up-Down — {uc.name}</div>
                                {(m.updown_allocations || []).filter((a: any) => !a.cluster_id || a.cluster_id === uc.id).length === 0 ? (
                                  <div style={{ padding: '12px 14px', textAlign: 'center', color: '#a3a398', fontSize: 12, background: '#fafaf8', borderRadius: 10, border: '1px solid #f0ede7' }}>No allocations for this cluster</div>
                                ) : (
                                  (m.updown_allocations || []).filter((a: any) => !a.cluster_id || a.cluster_id === uc.id).map((alloc: any) => {
                                    const isCmp = alloc.work_status === 'completed';
                                    const isFut = alloc.allocated_date && alloc.allocated_date > new Date().toISOString().slice(0, 10);
                                    const ss = isCmp ? { bg: '#f0fdf4', border: '#bbf7d0', color: '#16a34a', label: '✓ Done' } : isFut ? { bg: '#eff6ff', border: '#bfdbfe', color: '#1d4ed8', label: '📅 Upcoming' } : { bg: '#fef9c3', border: '#fde68a', color: '#b45309', label: '⏳ Pending' };
                                    const gross = isCmp && alloc.actual_gross != null ? alloc.actual_gross : alloc.gross_estimate;
                                    const transport = isCmp && alloc.actual_transport != null ? alloc.actual_transport : alloc.transport_estimate;
                                    const net = isCmp && alloc.actual_net != null ? alloc.actual_net : alloc.net_estimate;
                                    return (
                                      <div key={alloc.allocation_id} style={{ background: ss.bg, border: `1px solid ${ss.border}`, borderRadius: 10, padding: '10px 12px', marginBottom: 8 }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                                          <div><div style={{ fontWeight: 700, fontSize: 12 }}>{alloc.activity_name}</div><div style={{ fontSize: 10, color: '#6b7280', marginTop: 1 }}>👨‍🌾 {alloc.farmer_name} · #{alloc.job_id}</div></div>
                                          <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 999, fontWeight: 700, background: ss.bg, color: ss.color, border: `1px solid ${ss.border}`, whiteSpace: 'nowrap', marginLeft: 6 }}>{ss.label}</span>
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5 }}>
                                          {[{ label: !isCmp ? 'Gross (est.)' : 'Gross', val: `₹${Number(gross).toLocaleString('en-IN',{maximumFractionDigits:0})}`, sub: `${alloc.actual_area_done??alloc.allocated_area}ac×₹${alloc.mukkadam_rate}`, color: '#0f766e', bg: '#f0fdf4' },
                                            { label: !isCmp ? 'Transport (est.)' : 'Transport', val: Number(transport)>0 ? `+₹${Number(transport).toLocaleString('en-IN',{maximumFractionDigits:0})}` : '—', sub: Number(transport)>0 ? 'per assignment' : 'N/A', color: '#0369a1', bg: '#eff6ff' },
                                            { label: !isCmp ? 'Net (est.)' : 'Net Payable', val: `₹${Number(net).toLocaleString('en-IN',{maximumFractionDigits:0})}`, sub: !isCmp ? 'estimate' : 'final', color: isCmp ? '#16a34a' : '#ea580c', bg: isCmp ? '#f0fdf4' : '#fff7ed' },
                                          ].map((cell, ci) => (
                                            <div key={ci} style={{ background: cell.bg, borderRadius: 6, padding: '5px 6px', textAlign: 'center' }}>
                                              <div style={{ fontSize: 9, color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', marginBottom: 1 }}>{cell.label}</div>
                                              <div style={{ fontSize: 12, fontWeight: 800, color: cell.color }}>{cell.val}</div>
                                              <div style={{ fontSize: 9, color: '#9ca3af', marginTop: 1 }}>{cell.sub}</div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    );
                                  })
                                )}
                              </div>
                            ))}
                            {m.permanentClusters_m.map((pc: any) => (
                              <div key={pc.id} style={{ marginBottom: 16 }}>
                                <div style={{ fontSize: 10, fontWeight: 700, color: '#16a34a', textTransform: 'uppercase', marginBottom: 6 }}>🏠 Permanent — {pc.name} · Weekly ({m.weekly_payment_day_label ?? 'Saturday'})</div>
                                <div style={{ background: '#fafaf8', borderRadius: 10, border: '1px solid #f0ede7', overflow: 'hidden' }}>
                                  {(m.transaction_history ?? []).filter((t: any) => t.type === 'weekly').length === 0 && <div style={{ padding: '12px 16px', textAlign: 'center', color: '#a3a398', fontSize: 12 }}>No weekly payments yet</div>}
                                  {(m.transaction_history ?? []).filter((t: any) => t.type === 'weekly').map((w: any, j: number) => (
                                    <div key={j} style={{ padding: '10px 12px', borderBottom: '1px solid #f0ede7' }}>
                                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <div><div style={{ fontSize: 13, fontWeight: 600 }}>Weekly — {w.date?.slice(5).replace('-', ' ')}</div></div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(Math.abs(w.amount))}</span><Chip status="paid" /></div>
                                      </div>
                                    </div>
                                  ))}
                                  {(m.missed_weekly_dates ?? []).map((d: string, j: number) => (
                                    <div key={`mixmiss-${j}`} style={{ padding: '10px 12px', borderBottom: '1px solid #f0ede7', background: '#fefce8' }}>
                                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <div><div style={{ fontSize: 13, fontWeight: 600 }}>Weekly — {d.slice(5).replace('-', ' ')}</div><div style={{ fontSize: 10, color: '#dc2626', marginTop: 2 }}>⚠️ Missed</div></div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                          <span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(m.weekly_payment_amount ?? 0)}</span><Chip status="due" />
                                          <button onClick={e => { e.stopPropagation(); setPayModal({ mukkadam: m, assignmentId: m.assignmentId_m, defaultDate: d }); }} style={{ padding: '6px 16px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>💰 Pay</button>
                                        </div>
                                      </div>
                                    </div>
                                  ))}
                                  {m.weeklyDueToday_m && !m.alreadyPaidToday_m && (m.missed_weekly_dates ?? []).length === 0 && (
                                    <div style={{ padding: '10px 12px', background: '#fefce8' }}>
                                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <div><div style={{ fontSize: 13, fontWeight: 600 }}>Weekly Due Today</div></div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                          <span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(m.weeklyPayAmt_m ?? 0)}</span><Chip status="due" />
                                          <button onClick={e => { e.stopPropagation(); setPayModal({ mukkadam: m, assignmentId: m.assignmentId_m }); }} style={{ padding: '6px 16px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>💰 Pay</button>
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : m.isUpdown ? (
                          /* ── UPDOWN: show per-allocation transport breakdown ── */
                          <div>
                            <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', marginBottom: 8 }}>🚜 Allocations</div>
                            {(m.updown_allocations || []).length === 0 ? (
                              <div style={{ padding: 20, textAlign: 'center', color: '#a3a398', fontSize: 12, background: '#fafaf8', borderRadius: 10, border: '1px solid #f0ede7' }}>
                                No allocations assigned yet
                              </div>
                            ) : (m.updown_allocations || []).map((alloc: any) => {
                              const isCompleted = alloc.work_status === 'completed';
                              const isFuture    = alloc.allocated_date && alloc.allocated_date > new Date().toISOString().slice(0, 10);
                              const statusStyle = isCompleted
                                ? { bg: '#f0fdf4', border: '#bbf7d0', color: '#16a34a', label: '✓ Done' }
                                : isFuture
                                ? { bg: '#eff6ff', border: '#bfdbfe', color: '#1d4ed8', label: '📅 Upcoming' }
                                : { bg: '#fef9c3', border: '#fde68a', color: '#b45309', label: '⏳ Pending' };
                              const gross     = isCompleted && alloc.actual_gross     != null ? alloc.actual_gross     : alloc.gross_estimate;
                              const transport = isCompleted && alloc.actual_transport != null ? alloc.actual_transport : alloc.transport_estimate;
                              const net       = isCompleted && alloc.actual_net       != null ? alloc.actual_net       : alloc.net_estimate;
                              const isEst     = !isCompleted;
                              return (
                                <div key={alloc.allocation_id} style={{ background: statusStyle.bg, border: `1px solid ${statusStyle.border}`, borderRadius: 10, padding: '10px 12px', marginBottom: 8 }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                                    <div>
                                      <div style={{ fontWeight: 700, fontSize: 12, color: '#111827' }}>{alloc.activity_name}</div>
                                      <div style={{ fontSize: 10, color: '#6b7280', marginTop: 1 }}>👨‍🌾 {alloc.farmer_name} · #{alloc.job_id}{alloc.allocated_date ? ` · ${alloc.allocated_date}` : ''}</div>
                                    </div>
                                    <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 999, fontWeight: 700, background: statusStyle.bg, color: statusStyle.color, border: `1px solid ${statusStyle.border}`, whiteSpace: 'nowrap', marginLeft: 6 }}>{statusStyle.label}</span>
                                  </div>
                                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5 }}>
                                    {[
                                      { label: isEst ? 'Gross (est.)' : 'Gross', val: `₹${Number(gross).toLocaleString('en-IN',{maximumFractionDigits:0})}`, sub: `${alloc.actual_area_done??alloc.allocated_area}ac×₹${alloc.mukkadam_rate}`, color: '#0f766e', bg: '#f0fdf4' },
                                      { label: isEst ? 'Transport (est.)' : 'Transport', val: Number(transport)>0 ? `+₹${Number(transport).toLocaleString('en-IN',{maximumFractionDigits:0})}` : '—', sub: Number(transport)>0 ? 'per assignment' : 'N/A', color: '#0369a1', bg: '#eff6ff' },
                                      { label: isEst ? 'Net (est.)' : 'Net Payable', val: `₹${Number(net).toLocaleString('en-IN',{maximumFractionDigits:0})}`, sub: isEst ? 'estimate' : 'final', color: isCompleted ? '#16a34a' : '#ea580c', bg: isCompleted ? '#f0fdf4' : '#fff7ed' },
                                    ].map((cell, ci) => (
                                      <div key={ci} style={{ background: cell.bg, borderRadius: 6, padding: '5px 6px', textAlign: 'center' }}>
                                        <div style={{ fontSize: 9, color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', marginBottom: 1 }}>{cell.label}</div>
                                        <div style={{ fontSize: 12, fontWeight: 800, color: cell.color }}>{cell.val}</div>
                                        <div style={{ fontSize: 9, color: '#9ca3af', marginTop: 1 }}>{cell.sub}</div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          /* ── PERMANENT: weekly payment section ── */
                          <div>
                            <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', marginBottom: 8 }}>Weekly ({m.weekly_payment_day_label ?? 'Saturday'})</div>
                            <div style={{ background: '#fafaf8', borderRadius: 10, border: '1px solid #f0ede7', overflow: 'hidden' }}>
                              {(m.transaction_history ?? []).filter((t: any) => t.type === 'weekly').length === 0 && <div style={{ padding: 20, textAlign: 'center', color: '#a3a398', fontSize: 12 }}>No weekly payments yet</div>}
                              {(m.transaction_history ?? []).filter((t: any) => t.type === 'weekly').map((w: any, j: number) => (
                                <div key={j} style={{ padding: '10px 12px', borderBottom: '1px solid #f0ede7' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                    <div>
                                      <div style={{ fontSize: 13, fontWeight: 600 }}>Weekly — {w.date?.slice(5).replace('-', ' ')}</div>
                                      {w.notes && <div style={{ fontSize: 10, color: '#a3a398', marginTop: 2 }}>{w.notes}</div>}
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                      <span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(Math.abs(w.amount))}</span>
                                      <Chip status="paid" />
                                    </div>
                                  </div>
                                </div>
                              ))}
                              {(m.missed_weekly_dates ?? []).map((d: string, j: number) => (
                                <div key={`miss-${j}`} style={{ padding: '10px 12px', borderBottom: '1px solid #f0ede7', background: '#fefce8' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                    <div>
                                      <div style={{ fontSize: 13, fontWeight: 600 }}>Weekly — {d.slice(5).replace('-', ' ')}</div>
                                      <div style={{ fontSize: 10, color: '#dc2626', marginTop: 2 }}>⚠️ Missed</div>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                      <span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(m.weekly_payment_amount ?? 0)}</span>
                                      <Chip status="due" />
                                      <button onClick={e => { e.stopPropagation(); setPayModal({ mukkadam: m, assignmentId: m.assignmentId_m, defaultDate: d }); }} style={{ padding: '6px 16px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>💰 Pay</button>
                                    </div>
                                  </div>
                                </div>
                              ))}
                              {m.weeklyDueToday_m && !m.alreadyPaidToday_m && (m.missed_weekly_dates ?? []).length === 0 && (
                                <div style={{ padding: '10px 12px', background: '#fefce8', borderTop: (m.transaction_history ?? []).filter((t: any) => t.type === 'weekly').length > 0 ? '1px solid #f0ede7' : 'none' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                    <div>
                                      <div style={{ fontSize: 13, fontWeight: 600 }}>Weekly Due Today</div>
                                      <div style={{ fontSize: 10, color: '#a3a398' }}>{m.weekly_payment_day_label ?? 'Saturday'}</div>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                      <span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(m.weeklyPayAmt_m ?? 0)}</span>
                                      <Chip status="due" />
                                      <button onClick={e => { e.stopPropagation(); setPayModal({ mukkadam: m, assignmentId: m.assignmentId_m }); }} style={{ padding: '6px 16px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>💰 Pay</button>
                                    </div>
                                  </div>
                                </div>
                              )}
                              {!m.weeklyDueToday_m && !m.alreadyPaidToday_m && (m.missed_weekly_dates ?? []).length === 0 && (m.transaction_history ?? []).filter((t: any) => t.type === 'weekly').length > 0 && (
                                <div style={{ padding: '10px 12px', background: '#f0fdf4', borderTop: '1px solid #f0ede7', fontSize: 11, color: '#16a34a', textAlign: 'center', fontWeight: 600 }}>
                                  ✓ Next payment: {m.weekly_payment_day_label ?? 'Saturday'}
                                </div>
                              )}
                            </div>
                            <div style={{ marginTop: 4, padding: '6px 12px', fontSize: 11, color: '#0d9488', background: '#f0fdfa', borderRadius: 6, border: '1px solid #99f6e4' }}>
                              ℹ️ Weekly payments don't need admin verification — direct pay.
                            </div>
                          </div>
                        )}

                        {/* Payment Summary — always shown, different layout per type */}
                        {(() => {
                          const totalTransportSettl = (m.settlements ?? []).reduce((acc: number, st: any) => acc + Number(st.transport_deducted || 0), 0);
                          const totalGrossSettl     = (m.settlements ?? []).reduce((acc: number, st: any) => acc + Number(st.gross_amount || 0), 0);
                          const totalPaidOut        = (m.settlements ?? []).reduce((acc:number,st:any)=>acc+(st.payments_made||[]).reduce((s:number,p:any)=>s+Number(p.amount),0),0);
                          const remaining           = (m.settlements ?? []).reduce((acc:number,st:any)=>acc+Number(st.net_payable||0),0) - totalPaidOut;
                          const depositHeldNow      = (m.settlements ?? []).filter((st: any) => { const a = st.activities||[]; return !(a.length>0 && a.every((x:any)=>x.work_status==='completed')); }).reduce((acc:number,st:any)=>acc+Number(st.deposit_held||0),0);
                          return (
                            <div style={{ marginTop: 14, background: '#f5f3ff', borderRadius: 10, padding: 14, border: '1px solid #ddd6fe' }}>
                              <div style={{ fontSize: 11, fontWeight: 700, color: '#7c3aed', marginBottom: 8 }}>💰 Payment Summary</div>
                              {m.isUpdown ? (
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '4px 12px', fontSize: 12 }}>
                                  <span style={{ color: '#6b6b63' }}>Gross Earned</span>
                                  <span style={{ fontWeight: 700, color: '#0f766e', textAlign: 'right' }}>{fmt(totalGrossSettl)}</span>
                                  {totalTransportSettl > 0 && <>
                                    <span style={{ color: '#6b6b63' }}>+ Transport (all allocs)</span>
                                    <span style={{ fontWeight: 700, color: '#0369a1', textAlign: 'right' }}>+{fmt(totalTransportSettl)}</span>
                                  </>}
                                  <span style={{ color: '#6b6b63' }}>Net Payable</span>
                                  <span style={{ fontWeight: 700, color: '#dc2626', textAlign: 'right' }}>{fmt(totalGrossSettl + totalTransportSettl)}</span>
                                  {totalPaidOut > 0 && <>
                                    <span style={{ color: '#6b6b63' }}>Paid Out</span>
                                    <span style={{ fontWeight: 700, color: '#16a34a', textAlign: 'right' }}>−{fmt(totalPaidOut)}</span>
                                  </>}
                                  <span style={{ color: '#6b6b63', fontWeight: 700, borderTop: '1px solid #ddd6fe', paddingTop: 4 }}>Remaining</span>
                                  <span style={{ fontWeight: 800, textAlign: 'right', borderTop: '1px solid #ddd6fe', paddingTop: 4, color: remaining > 0.01 ? '#dc2626' : '#16a34a' }}>{remaining > 0.01 ? fmt(remaining) : '✓ Clear'}</span>
                                </div>
                              ) : (
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '4px 12px', fontSize: 12 }}>
                                  <span style={{ color: '#6b6b63' }}>Gross Earned</span>
                                  <span style={{ fontWeight: 700, color: '#0f766e', textAlign: 'right' }}>{fmt(totalGrossSettl)}</span>
                                  {depositHeldNow > 0 && <>
                                    <span style={{ color: '#6b6b63' }}>10% Deposit held</span>
                                    <span style={{ fontWeight: 700, color: '#b45309', textAlign: 'right' }}>{fmt(depositHeldNow)} held</span>
                                  </>}
                                  <span style={{ color: '#6b6b63' }}>Advance</span>
                                  <span style={{ fontWeight: 700, color: '#16a34a', textAlign: 'right' }}>{fmt(m.advance_amount ?? 0)}</span>
                                  <span style={{ color: '#6b6b63' }}>Weekly Paid</span>
                                  <span style={{ fontWeight: 700, color: '#16a34a', textAlign: 'right' }}>{fmt(m.weeklyPaid)}</span>
                                  <span style={{ color: '#6b6b63' }}>Settlements Paid</span>
                                  <span style={{ fontWeight: 700, color: '#2563eb', textAlign: 'right' }}>{fmt(m.settlePaid)}</span>
                                  {m.adhocTot > 0 && <>
                                    <span style={{ color: '#6b6b63' }}>Ad-hoc / Manual</span>
                                    <span style={{ fontWeight: 700, color: '#7c3aed', textAlign: 'right' }}>{fmt(m.adhocTot)}</span>
                                  </>}
                                  <span style={{ color: '#6b6b63', fontWeight: 700, borderTop: '1px solid #ddd6fe', paddingTop: 4 }}>Total Outflows</span>
                                  <span style={{ fontWeight: 800, textAlign: 'right', borderTop: '1px solid #ddd6fe', paddingTop: 4 }}>{fmt(m.totalOut)}</span>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    </div>
                  </div>
                )}

                {/* ── TAB: MANUAL ENTRIES ── */}
                {currentTab === 'adhoc' && (() => {
                  // Need at least one settlement to attach misc cost to
                  const settls = m.settlements ?? [];
                  const af = adhocForm[m.mukkadam_id] || {};
                  const setAf = (patch: any) => setAdhocForm((prev: any) => ({ ...prev, [m.mukkadam_id]: { ...(prev[m.mukkadam_id] || {}), ...patch } }));
                  const isSaving = adhocSaving === m.mukkadam_id;

                  const submitMiscCost = async () => {
  const amount = parseFloat(af.amount || '0');
  const reason = (af.reason || '').trim();

  if (!amount || amount <= 0) { alert('Enter a valid amount'); return; }
  if (!reason)                { alert('Enter a reason'); return; }

  setAdhocSaving(m.mukkadam_id);
  const token = localStorage.getItem('auth_token');

  try {
    // If there's a job/settlement available use job-linked endpoint, else use mukkadam-only
    const jobId = af.job_id || settls[0]?.job_id;
    const url = jobId
      ? `${API_BASE_URL}/api/mukkadam/${m.mukkadam_id}/job/${jobId}/misc/`
      : `${API_BASE_URL}/api/mukkadam/${m.mukkadam_id}/misc/`;

    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
      body: JSON.stringify({
        amount,
        reason: `${af.type || 'Manual Entry'}: ${reason}`,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      alert(err.error || 'Failed');
      return;
    }

    const newCost = await res.json();
    m.miscCosts.unshift(newCost);

    setShowAddEntry(null);
    setAdhocForm((prev: any) => {
      const n = { ...prev };
      delete n[m.mukkadam_id];
      return n;
    });

    (m._clusters ?? [{ id: m._cluster_id }]).forEach((c: any) => reloadCluster(c.id));

  } catch {
    alert('Network error');
  } finally {
    setAdhocSaving(null);
  }
};
                  return (
                  <div style={{ padding: '14px 16px' }}>
                    <div onClick={() => setShowAddEntry(showAddEntry === m.mukkadam_id ? null : m.mukkadam_id)} style={{ padding: '16px 20px', borderRadius: 12, cursor: 'pointer', border: '2px dashed #ddd6fe', background: showAddEntry === m.mukkadam_id ? '#f5f3ff' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 14 }}
                      onMouseEnter={e => { if (showAddEntry !== m.mukkadam_id) (e.currentTarget as HTMLDivElement).style.background = '#f5f3ff'; }}
                      onMouseLeave={e => { if (showAddEntry !== m.mukkadam_id) (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                    >
                      <span style={{ fontSize: 24, color: '#7c3aed' }}>+</span>
                      <div><div style={{ fontSize: 14, fontWeight: 700, color: '#7c3aed' }}>Add Manual Entry</div><div style={{ fontSize: 11, color: '#6b6b63' }}>Wedding advance, bonus, adjustment, deduction, or any off-schedule payment</div></div>
                    </div>
                    {showAddEntry === m.mukkadam_id && (
                      <div onClick={e => e.stopPropagation()} style={{ background: '#f5f3ff', borderRadius: 12, padding: 18, border: '1px solid #ddd6fe', marginBottom: 14 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: '#7c3aed', marginBottom: 12 }}>New Manual Entry</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                          <div>
                            <div style={{ fontSize: 11, color: '#6b6b63', marginBottom: 4, fontWeight: 600 }}>Type</div>
                            <select value={af.type || 'Wedding Advance'} onChange={e => setAf({ type: e.target.value })}
                              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, background: '#fff', fontFamily: 'inherit' }}>
                              <option>Wedding Advance</option>
                              <option>Extra Payment</option>
                              <option>Festival Bonus</option>
                              <option>Deduction</option>
                              <option>Adjustment</option>
                              <option>Other</option>
                            </select>
                          </div>
                          <div>
                            <div style={{ fontSize: 11, color: '#6b6b63', marginBottom: 4, fontWeight: 600 }}>Amount (₹)</div>
                            <input type="number" placeholder="Enter amount" value={af.amount || ''} onChange={e => setAf({ amount: e.target.value })}
                              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, boxSizing: 'border-box' as const, fontFamily: 'inherit' }} />
                          </div>
                          {settls.length > 1 && (
                            <div style={{ gridColumn: '1 / -1' }}>
                              <div style={{ fontSize: 11, color: '#6b6b63', marginBottom: 4, fontWeight: 600 }}>Job (settlement to link)</div>
                              <select value={af.job_id || settls[0]?.job_id} onChange={e => setAf({ job_id: e.target.value })}
                                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, background: '#fff', fontFamily: 'inherit' }}>
                                {settls.map((s: any) => (
                                  <option key={s.job_id} value={s.job_id}>#{s.job_id} — {s.farmer_name}</option>
                                ))}
                              </select>
                            </div>
                          )}
                        </div>
                        <div style={{ marginTop: 12 }}>
                          <div style={{ fontSize: 11, color: '#6b6b63', marginBottom: 4, fontWeight: 600 }}>Note / Reason *</div>
                          <input placeholder="Why is this payment being made..." value={af.reason || ''} onChange={e => setAf({ reason: e.target.value })}
                            style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, boxSizing: 'border-box' as const, fontFamily: 'inherit' }} />
                        </div>
                        
                        <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 8, background: '#fff7ed', border: '1px solid #fed7aa', fontSize: 11, color: '#ea580c' }}>
                          🔐 This entry will be submitted for <strong>Payment Admin verification</strong> before payment is released.
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
                          <button onClick={() => { setShowAddEntry(null); setAf({}); }} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e8e5de', background: '#fff', color: '#6b6b63', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>Cancel</button>
                          <button onClick={submitMiscCost} disabled={isSaving }
                            style={{ padding: '8px 24px', borderRadius: 8, border: 'none', background: isSaving ? '#a78bfa' : '#7c3aed', color: '#fff', fontSize: 13, fontWeight: 700, cursor: isSaving ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}>
                            {isSaving ? 'Saving...' : 'Submit for Verification'}
                          </button>
                        </div>
                      </div>
                    )}
                    {m.miscCosts.length === 0 && showAddEntry !== m.mukkadam_id ? (
                      <div style={{ padding: 32, textAlign: 'center', color: '#a3a398' }}>No manual entries yet.</div>
                    ) : m.miscCosts.length > 0 && (
                      <div style={{ background: '#fafaf8', borderRadius: 10, border: '1px solid #f0ede7', overflow: 'hidden' }}>
                        {m.miscCosts.map((e: any, j: number) => (
                          <div key={j} style={{ padding: '12px 14px', borderBottom: j < m.miscCosts.length - 1 ? '1px solid #f0ede7' : 'none' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div>
                                <div style={{ fontSize: 13, fontWeight: 600 }}>{e.reason}</div>
                                <div style={{ fontSize: 10, color: '#a3a398', marginTop: 4 }}>{e.created_at?.slice(0, 10)}</div>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span style={{ fontSize: 15, fontWeight: 700 }}>{fmt(e.amount)}</span>
                                {e.verified
                                  ? <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#f0fdf4', color: '#16a34a', fontWeight: 600, border: '1px solid #bbf7d0' }}>✓ Verified</span>
                                  : <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#fff7ed', color: '#ea580c', fontWeight: 600, border: '1px solid #fed7aa' }}>⏳ Pending</span>
                                }
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  );
                })()}

                {/* ── TAB: RECONCILIATION ── */}
                {currentTab === 'recon' && (
                  <div style={{ padding: '14px 16px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                      <div style={{ background: '#f0fdf4', borderRadius: 10, padding: 14, border: '1px solid #bbf7d0' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: '#16a34a', marginBottom: 10 }}>📊 SYSTEM-CALCULATED (Earned)</div>
                        <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                          {(m.settlements ?? []).map((s: any, i: number) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between' }}><span>{s.farmer_name} ({s.job_id})</span><span style={{ fontWeight: 700 }}>{fmt(s.gross_amount)}</span></div>
                          ))}
                          <div style={{ borderTop: '1px solid #bbf7d0', paddingTop: 4, marginTop: 2, display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
                            <span>Total Earned</span>
                            <span style={{ fontSize: 16, color: '#16a34a' }}>{fmt((m.settlements ?? []).reduce((s: number, x: any) => s + x.gross_amount, 0))}</span>
                          </div>
                        </div>
                      </div>
                      <div style={{ background: '#fff7ed', borderRadius: 10, padding: 14, border: '1px solid #fed7aa' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: '#ea580c', marginBottom: 10 }}>💸 ACTUAL OUTFLOWS</div>
                        <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Structured payments</span><span style={{ fontWeight: 600 }}>{fmt(m.structuredPaid)}</span></div>
                          {m.adhocTot > 0 && <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Ad-hoc / Manual</span><span style={{ fontWeight: 600, color: '#7c3aed' }}>{fmt(m.adhocTot)}</span></div>}
                          <div style={{ borderTop: '1px solid #fed7aa', paddingTop: 4, marginTop: 2, display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
                            <span>Total Outflows</span>
                            <span style={{ fontSize: 16, color: '#ea580c' }}>{fmt(m.totalOut)}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                    {(() => {
                      const earned  = (m.settlements ?? []).reduce((s: number, x: any) => s + x.gross_amount, 0);
                      const diff    = m.totalOut - earned;
                      const isOver  = diff > 5000;
                      const isUnder = diff < -5000;
                      return (
                        <div style={{ marginTop: 14, padding: 14, borderRadius: 10, background: isOver ? '#fef2f2' : isUnder ? '#fefce8' : '#f0fdf4', border: `1.5px solid ${isOver ? '#fecaca' : isUnder ? '#fde68a' : '#bbf7d0'}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 700, color: isOver ? '#dc2626' : isUnder ? '#ca8a04' : '#16a34a' }}>{isOver ? '⚠️ OVERPAID' : isUnder ? '📉 UNDERPAID' : '✅ WITHIN RANGE'}</div>
                            <div style={{ fontSize: 11, color: '#6b6b63', marginTop: 2 }}>{!isOver && !isUnder ? 'Difference within expected range.' : isOver ? 'More paid than earned.' : 'Significant earnings gap — settlements pending.'}</div>
                          </div>
                          <div style={{ fontSize: 22, fontWeight: 800, color: isOver ? '#dc2626' : isUnder ? '#ca8a04' : '#16a34a' }}>{diff > 0 ? '+' : ''}{fmt(Math.abs(diff))}</div>
                        </div>
                      );
                    })()}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {/* ── Recent Weekly Payments ── */}
      {recent.length > 0 && (
        <div style={{ marginTop: 24, marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{ fontSize: 14 }}>✅</span>
            <span style={{ fontSize: 13, fontWeight: 700 }}>Recent Weekly Payments</span>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {recent.map((p: any, i: number) => (
              <div key={i} style={{ background: '#fff', borderRadius: 12, padding: '12px 16px', border: '1px solid #bbf7d0', minWidth: 200, flex: '1 1 200px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div><div style={{ fontSize: 13, fontWeight: 600 }}>{p.mukkadam_name}</div><div style={{ fontSize: 11, color: '#a3a398' }}>{p.cluster_name} · {p.crew_size} crew</div></div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: '#16a34a' }}>{fmt(p.amount)}</div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: '#6b6b63' }}>
                  <span>{p.payment_date?.slice(5).replace('-', ' ')}</span>
                  <span style={{ padding: '1px 8px', borderRadius: 5, fontSize: 10, fontWeight: 600, background: p.mode === 'UPI' ? '#ede9fe' : p.mode === 'CASH' ? '#fefce8' : '#eff6ff', color: p.mode === 'UPI' ? '#7c3aed' : p.mode === 'CASH' ? '#ca8a04' : '#2563eb' }}>{p.mode}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Weekly Pay Modal ── */}
      {payModal && (
        <WeeklyPayModal
          mukkadam={payModal.mukkadam}
          assignmentId={payModal.assignmentId}
          defaultDate={payModal.defaultDate}
          onClose={() => setPayModal(null)}
          onSaved={() => {
            setPayModal(null);
            (payModal.mukkadam._clusters ?? [{ id: payModal.mukkadam._cluster_id }]).forEach((c: any) => reloadCluster(c.id));
          }}
        />
      )}

      {/* ── Settlement Pay Modal ── */}
      {settlPayModal && (
        <SettlementPayModal
          mukkadam={settlPayModal.mukkadam}
          jobId={settlPayModal.jobId}
          netPayable={settlPayModal.amount}
          farmerName={settlPayModal.farmerName}
          onClose={() => setSettlPayModal(null)}
          onSaved={() => {
            setSettlPayModal(null);
            (settlPayModal.mukkadam._clusters ?? [{ id: settlPayModal.mukkadam._cluster_id }]).forEach((c: any) => reloadCluster(c.id));
          }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// WEEKLY PAY MODAL  — POST /api/weekly-payment/add/
// ─────────────────────────────────────────────────────────────────────────────

function WeeklyPayModal({ mukkadam, assignmentId, defaultDate, onClose, onSaved }: {
  mukkadam: any; assignmentId: number; defaultDate?: string;
  onClose: () => void; onSaved: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate]     = useState(defaultDate ?? today);
  const [amount, setAmount] = useState(String(mukkadam.weekly_payment_amount ?? ''));
  const [mode, setMode]     = useState('CASH');
  const [notes, setNotes]   = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const isLate = !!defaultDate;

  const handleSave = async () => {
    setSaving(true); setError('');
    try {
      const token      = localStorage.getItem('auth_token') || '';
      const finalNotes = isLate
        ? (notes ? `${notes} (late — was due ${date})` : `Late payment — was due ${date}`)
        : notes;
      const res = await fetch(`${API_BASE_URL}/api/weekly-payment/add/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
        body: JSON.stringify({
          assignment_id: assignmentId,
          amount:        parseFloat(amount),
          payment_date:  date,
          mode,
          notes:         finalNotes,
        }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Payment failed');
      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }} onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: 16, width: 400, boxShadow: '0 20px 60px rgba(0,0,0,.2)', padding: '24px' }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>📅 {isLate ? 'Late ' : ''}Weekly Payment</div>
        <div style={{ fontSize: 12, color: '#a3a398', marginBottom: 16 }}>{mukkadam.mukkadam_name} · {mukkadam.crew_size} crew</div>

        <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, padding: '10px 12px', marginBottom: 16, textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: '#6b7280', marginBottom: 2, textTransform: 'uppercase', fontWeight: 600 }}>WEEKLY AMOUNT</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#1d4ed8' }}>₹{Number(amount || 0).toLocaleString('en-IN')}</div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: '#6b6b63', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Amount (₹)</label>
            <input value={amount} onChange={e => setAmount(e.target.value)} type="number"
              style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 14, fontFamily: 'inherit', marginTop: 4, boxSizing: 'border-box' as const }} />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: '#6b6b63', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Payment Date</label>
            <input value={date} onChange={e => setDate(e.target.value)} type="date"
              style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, fontFamily: 'inherit', marginTop: 4, boxSizing: 'border-box' as const }} />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: '#6b6b63', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Mode</label>
            <select value={mode} onChange={e => setMode(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, fontFamily: 'inherit', marginTop: 4, boxSizing: 'border-box' as const, background: '#fff' }}>
              {['CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE'].map(m => (
                <option key={m} value={m}>{m === 'ZOHO_PAYMENT' ? 'Zoho Payment' : m === 'BANK_TRANSFER' ? 'Bank Transfer' : m}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: '#6b6b63', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Notes (optional)</label>
            <input value={notes} onChange={e => setNotes(e.target.value)} placeholder="e.g. Cash given on site"
              style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, fontFamily: 'inherit', marginTop: 4, boxSizing: 'border-box' as const }} />
          </div>
          {error && <div style={{ color: '#dc2626', fontSize: 12 }}>❌ {error}</div>}
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 20 }}>
          <button onClick={onClose} disabled={saving}
            style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e8e5de', background: '#fff', color: '#6b6b63', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving}
            style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: saving ? '#bfdbfe' : '#1d4ed8',
              color: '#fff', fontSize: 13, fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}>
            {saving ? 'Saving...' : `✓ Record ₹${Number(amount || 0).toLocaleString('en-IN')}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SETTLEMENT PAY MODAL  — POST /api/mukkadam/{id}/settlement/{jobId}/pay/
// ─────────────────────────────────────────────────────────────────────────────

function SettlementPayModal({ mukkadam, jobId, netPayable, farmerName, onClose, onSaved }: {
  mukkadam: any; jobId: string; netPayable: number; farmerName: string;
  onClose: () => void; onSaved: () => void;
}) {
  const [mode, setMode]     = useState('CASH');
  const [notes, setNotes]   = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const handlePay = async () => {
    setSaving(true); setError('');
    try {
      const token = localStorage.getItem('auth_token') || '';
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadam.mukkadam_id}/settlement/${jobId}/pay/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
          body: JSON.stringify({ mode, notes }),
        }
      );
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Payment failed');
      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
      onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: 16, width: 380, boxShadow: '0 20px 60px rgba(0,0,0,.25)', padding: '24px' }}
        onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>🏦 Pay Mukkadam</div>
        <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 16 }}>
          <strong>{mukkadam.mukkadam_name}</strong> · Job #{jobId} · {farmerName}
        </div>

        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '10px 12px', marginBottom: 16, textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: '#6b7280', marginBottom: 2, textTransform: 'uppercase', fontWeight: 600 }}>NET PAYABLE</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: '#0f766e' }}>₹{Math.round(netPayable).toLocaleString('en-IN')}</div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: 4 }}>Payment Mode</label>
            <select value={mode} onChange={e => setMode(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: 8, fontSize: 13, background: '#fff', boxSizing: 'border-box' as const, fontFamily: 'inherit' }}>
              {['CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE'].map(m => (
                <option key={m} value={m}>{m === 'ZOHO_PAYMENT' ? 'Zoho Payment' : m === 'BANK_TRANSFER' ? 'Bank Transfer' : m}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: 4 }}>Notes (optional)</label>
            <input value={notes} onChange={e => setNotes(e.target.value)} placeholder="e.g. UPI ref 12345"
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: 8, fontSize: 13, fontFamily: 'inherit', boxSizing: 'border-box' as const }} />
          </div>
          {error && <div style={{ color: '#dc2626', fontSize: 12 }}>❌ {error}</div>}
        </div>

        <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
          <button onClick={onClose} disabled={saving}
            style={{ flex: 1, padding: '10px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>Cancel</button>
          <button onClick={handlePay} disabled={saving}
            style={{ flex: 2, padding: '10px', borderRadius: 8, border: 'none',
              background: saving ? '#99f6e4' : '#14b8a6',
              color: '#fff', fontWeight: 700, fontSize: 13,
              cursor: saving ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}>
            {saving ? 'Processing...' : `✓ Confirm Pay ₹${Math.round(netPayable).toLocaleString('en-IN')}`}
          </button>
        </div>
      </div>
    </div>
  );
}