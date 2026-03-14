// components/DayDetailModal.tsx
import React, { useEffect } from 'react';
import { X,Plus,Users,AlertTriangle, Pencil } from 'lucide-react';
import { Allocation, Job, Mukkadam } from '../types/types';
// import './Day.css';
import { Tractor, User, AlertCircle } from 'lucide-react';
import { useState } from 'react';
// import { toast } from './ui/sonner';
import { toast } from './ui/sonner';
import { API_BASE_URL } from '@/types/config';
type PotentialStatus = 'PARTIAL' | 'NONE';
import { createPortal } from "react-dom";

import LeaveModal from './leave'; // Import your leave modal component
import ReactDOM from 'react-dom';
import { JobNoteModal } from './JobNoteModel';
import { useCurrentUser } from '../hooks/currentUser';
import { notifyWhatsAppGroup } from '@/utils/whatsapp';
import { useAuth } from '@/context/auth';

// TagChip component
const TagChip: React.FC<{ tagKey: string; small?: boolean }> = ({ tagKey, small }) => {
  const tagColors: Record<string, { bg: string; text: string }> = {
    bug: { bg: '#fee2e2', text: '#dc2626' },
    urgent: { bg: '#fef3c7', text: '#d97706' },
    feedback: { bg: '#dbeafe', text: '#0284c7' },
    blocked: { bg: '#f3e8ff', text: '#7c3aed' },
    info: { bg: '#e0e7ff', text: '#4f46e5' },
  };
  const style = tagColors[tagKey] || { bg: '#f3f4f6', text: '#6b7280' };
  return (
    <span
      className={small ? 'text-[10px]' : 'text-xs'}
      style={{
        display: 'inline-block',
        padding: small ? '3px 8px' : '4px 10px',
        borderRadius: '12px',
        background: style.bg,
        color: style.text,
        fontWeight: 600,
      }}
    >
      {tagKey}
    </span>
  );
};

// Helper function for rendering text with mentions
const renderTextWithMentions = (text: string, mentionIds: number[], currentUserId: number) => {
  return text;
};

// Helper function for time ago
const timeAgo = (dateStr: string) => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
};
interface CalendarFilters {
  farmerId: string | null;
  mukkadamId: number | null;
  dateFrom: string | null;
  dateTo: string | null;
  plotId: number | null;          // ✅ ADD
  activityId: number | null;      // ✅ ADD
  cropName: string | null;        // ✅ ADD
  variety: string | null;         // ✅ ADD
}
interface PotentialJob {
  date: string;          // suggested potential date (same logic as JobDetailPanel)
  activityId: number;
  activityName: string;
  status: PotentialStatus;
  cropName: string;
  variety: string;
  bookedArea: number;
  unbookedArea: number;
  bookedRate: number;
  clusterRate: number;
  farmerId: string;
  farmerName: string;
  plotId: number;
  potentialRevenue: number;
  plotName: string;
  jobId: string;
}

type MaxWorkRow = {
  mukkadamId: number;
  mukkadamName: string;
  activityId: number;
  activityName: string;
  productivity: number;
  availableWorkers: number;
  maxArea: number;
};

interface DayDetailModalProps {
  date: Date;
  allocations: Allocation[];
  mukkadams: Mukkadam[];
  capacitySummary: {
    used: number;
    total: number;
    percentage: number;
    conflicts: any[];
    mukkadamsOnLeave: number;
  };
   potentialJobs?: PotentialJob[];
  overloads: any[];    
  jobs: Job[];
  onLeavesUpdated?: () => void;



  leaves: any[];
  filters?: CalendarFilters;  // ✅ ADD THIS
  allJobs?: Job[]; 
  onClose: () => void;
  // To:
viewMode: string | string[];
  // In DayDetailModalProps — revert to:
onAllocationDateChange: (job: Job, allocation: Allocation) => void;
onAllocationDelete: (allocation: Allocation) => void;
  onStartAllocation: (jobId: string, activityId: number, activity: any) => void;
  clusterId: number; // ✅ ADD THIS - to look up job details
}
// ── helper types ──────────────────────────────────────────────────────────────
interface AllocationWithReport extends Allocation {
  report_submitted?: boolean;
  allows_second_job?:boolean;
  actual_area_done?: number | null;
  actual_crew_size?: number | null;
  actual_start_time?: string | null;
  actual_end_time?: string | null;
  report_submitted_at?: string | null;
  farmer_agreed?: boolean | null;
  farmer_response_at?: string | null;
  farmer_dispute_reason?: string | null;
  use_actual_for_settlement?: boolean;
  is_carry_forward?: boolean;
  notes?: string;
}
// simple example implementation
type CapBarProps = {
  used: number;
  total: number;
  size?: 'sm' | 'md';
  showLabel?: boolean;
};

const CapBar: React.FC<CapBarProps> = ({ used, total, size = 'md', showLabel = true }) => {
  const pct = total > 0 ? Math.min((used / total) * 100, 120) : 0;
  const heightClass = size === 'sm' ? 'h-1.5' : 'h-2.5';

  return (
    <div className={`w-full ${heightClass} rounded-full bg-stone-100 overflow-hidden`}>
      <div
        className={`${heightClass} rounded-full bg-emerald-500 transition-all`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
};


// In JobNoteModal.tsx — replace the NotesTabBody export with this version
// The only change is adding job context (activity name + farmer name) to each note card

export const NotesTabBody: React.FC<{
  dayNotes: any[];
  notesLoading: boolean;
  currentUserId: number;
  onOpenNoteForJob: (jobId: string, label: string) => void;
  jobsOnThisDay: any[];
  isoDate: string;
}> = ({ dayNotes, notesLoading, currentUserId, onOpenNoteForJob, jobsOnThisDay, isoDate }) => {

  const unresolved = dayNotes.filter(n => !n.is_resolved);
  const resolved   = dayNotes.filter(n =>  n.is_resolved);

  // ✅ Build a lookup: job_id → "ActivityName · FarmerName"
// and multiple plots — so we store ALL activity+plot combos per job_id
const jobLabelMap: Record<string, string[]> = {};

jobsOnThisDay.forEach(job => {
  (job.activities || [])
    .filter((act: any) => act.scheduled_date?.slice(0, 10) === isoDate)
    .forEach((act: any) => {
      // plot name: activity-level first, then job-level fallback
      const plotName =
        act.plot_name ||
        act.plot_code ||
        job.plot_name ||
        job.plot_code ||
        null;

      const label = [
        act.activity_name,
        job.farmer_name,
        plotName ? `📍 ${plotName}` : null,
      ]
        .filter(Boolean)
        .join(' · ');

      if (!jobLabelMap[job.job_id]) jobLabelMap[job.job_id] = [];

      // avoid duplicate labels if same activity appears twice
      if (!jobLabelMap[job.job_id].includes(label)) {
        jobLabelMap[job.job_id].push(label);
      }
    });

  // fallback if no activities matched the date filter
  if (!jobLabelMap[job.job_id] || jobLabelMap[job.job_id].length === 0) {
    const plotName = job.plot_name || job.plot_code || null;
    jobLabelMap[job.job_id] = [
      [job.farmer_name, plotName ? `📍 ${plotName}` : null]
        .filter(Boolean)
        .join(' · ') || job.job_id,
    ];
  }
});

// Helper: returns a single display string (joins multiple activities with comma)
const getJobLabel = (jobId: string): string =>
  (jobLabelMap[jobId] || [`Job #${jobId}`]).join(', ');


// ── Also update the "Add note to job" quick buttons to include plot ──────────
// Replace the jobsOnThisDay.flatMap block with:

{jobsOnThisDay.flatMap(job =>
  (job.activities || [])
    .filter((act: any) => act.scheduled_date?.slice(0, 10) === isoDate)
    .map((act: any) => {
      const plotName =
        act.plot_name || act.plot_code || job.plot_name || job.plot_code || null;

      const label = [
        act.activity_name,
        job.farmer_name,
        plotName ? `📍 ${plotName}` : null,
      ]
        .filter(Boolean)
        .join(' – ');

      return (
        <button
          key={`${job.job_id}-${act.id}`}
          onClick={() => onOpenNoteForJob(job.job_id, label)}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-indigo-200 bg-indigo-50 text-indigo-700 text-xs font-semibold rounded-lg hover:bg-indigo-100 transition"
        >
          <Pencil size={11} />
          {label}
        </button>
      );
    })
)}
  return (
    <div className="space-y-4">

      {/* Quick-add buttons per job */}
      <div>
        <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">
          Add note to job
        </p>
        <div className="flex flex-wrap gap-2">
          {jobsOnThisDay.flatMap(job =>
            (job.activities || [])
              .filter((act: any) => act.scheduled_date?.slice(0, 10) === isoDate)
              .map((act: any) => (
                <button
                  key={`${job.job_id}-${act.id}`}
                  onClick={() =>
                    onOpenNoteForJob(job.job_id, `${act.activity_name} – ${job.farmer_name}`)
                  }
                  className="flex items-center gap-1.5 px-3 py-1.5 border border-indigo-200 bg-indigo-50 text-indigo-700 text-xs font-semibold rounded-lg hover:bg-indigo-100 transition"
                >
                  <Pencil size={11} />
                  {act.activity_name} · {job.farmer_name}
                </button>
              ))
          )}
        </div>
      </div>

      {dayNotes.length === 0 && (
        <p className="text-sm text-gray-400 italic text-center py-6">
          No notes for today. Click a job above to add one.
        </p>
      )}

      {/* Unresolved */}
      {unresolved.length > 0 && (
        <div>
          <p className="text-[10px] font-bold text-red-500 uppercase tracking-wider mb-2">
            🔥 Open Issues ({unresolved.length})
          </p>
          <div className="space-y-2">
            {unresolved.map((n: any) => {
              const isMentioned = n.mentions?.some((m: any) => m.id === currentUserId);
              const jobLabel = getJobLabel(n.job_id);

              return (
                <div
                  key={n.id}
                  className={`rounded-xl border overflow-hidden ${
                    isMentioned
                      ? 'border-blue-300 bg-blue-50/50 ring-1 ring-blue-200'
                      : 'border-red-100 bg-white'
                  }`}
                >
                  {/* ✅ Job context banner */}
                  <div className="px-3 py-1.5 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-gray-600 flex items-center gap-1">
                      📋 {jobLabel}
                    </span>
                    <span className="text-[10px] text-gray-400 font-mono">#{n.job_id}</span>
                  </div>

                  <div className="px-4 py-3">
                    {/* Tags + mention badge */}
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      {n.tags?.map((t: string) => <TagChip key={t} tagKey={t} small />)}
                      {isMentioned && (
                        <span className="text-[10px] font-bold text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded-full">
                          👋 You
                        </span>
                      )}
                    </div>

                    {/* Note text */}
                    <p className="text-sm text-gray-700 leading-relaxed">
                      {renderTextWithMentions(
                        n.text,
                        n.mentions?.map((m: any) => m.id) ?? [],
                        currentUserId
                      )}
                    </p>

                    {/* Footer */}
                    <p className="text-[10px] text-gray-400 mt-1.5 flex items-center gap-2">
                      <span>{n.author?.full_name}</span>
                      <span>·</span>
                      <span>{timeAgo(n.created_at)}</span>
                      <span>·</span>
                      <button
                        onClick={() => onOpenNoteForJob(n.job_id, jobLabel)}
                        className="text-indigo-500 hover:underline font-medium"
                      >
                        Open & resolve →
                      </button>
                    </p>

                    <span>·</span>
<button
  onClick={() => {
    notifyWhatsAppGroup(n, jobLabel, n.author?.full_name);
    toast.success('Message copied! Just paste & send in the group 📲');
  }}
  className="text-green-600 hover:underline font-medium flex items-center gap-1"
>
  📲 WhatsApp Group
</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Resolved */}
      {resolved.length > 0 && (
        <div>
          <p className="text-[10px] font-bold text-green-600 uppercase tracking-wider mb-2 mt-4">
            ✅ Resolved ({resolved.length})
          </p>
          <div className="space-y-2">
            {resolved.map((n: any) => {
              const jobLabel = getJobLabel(n.job_id);
              return (
                <div key={n.id} className="rounded-xl border border-green-200 bg-green-50/40 overflow-hidden opacity-75">
                  {/* ✅ Job context banner */}
                  <div className="px-3 py-1.5 bg-green-50 border-b border-green-100 flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-green-700 flex items-center gap-1">
                      📋 {jobLabel}
                    </span>
                    <span className="text-[10px] text-green-400 font-mono">#{n.job_id}</span>
                  </div>

                  <div className="px-4 py-3">
                    <div className="flex flex-wrap gap-1 mb-1">
                      {n.tags?.map((t: string) => <TagChip key={t} tagKey={t} small />)}
                    </div>
                    <p className="text-sm text-gray-500 line-through">{n.text}</p>
                    {n.resolution_note && (
                      <p className="text-xs text-green-700 italic mt-1">
                        ✅ {n.resolution_note}
                        {n.resolved_by?.full_name && ` — ${n.resolved_by.full_name}`}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};


const TeamDropdown: React.FC<{
  workerRows: any[];
  act: any;
  job: any;
  mukkadams: any[];
  onStartAllocation: (jobId: any, actId: any, actWithPrefill: any) => void;
}> = ({ workerRows, act, job, mukkadams, onStartAllocation }) => {
  const [open, setOpen] = useState(false);

  if (workerRows.length === 0) {
    return <span className="text-xs text-gray-400 italic">No team data</span>;
  }

  return (
    <div className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="text-xs px-2 py-1 border rounded bg-white hover:bg-gray-50 flex items-center gap-1"
      >
        <span>Teams</span>
        <span className="text-[10px] text-gray-500">▼</span>
      </button>

      {open && (
        <div className="absolute z-10 mt-1 w-56 bg-white border border-gray-200 rounded shadow-lg max-h-60 overflow-auto">
          <div className="p-1 space-y-1">
            {workerRows.map((r, i) => {
              const needed =
                r.productivity > 0
                  ? Math.ceil(Number(act.remaining_area) / r.productivity)
                  : 0;

              const canDo =
                needed > 0 &&
                needed <= r.availableWorkers &&
                r.availableWorkers > 0;

              const handleTeamClick = () => {
                // if (!canDo) return;
                const mukkadam = mukkadams.find(
                  mk => mk.mukkadam_id === r.mukkadamId
                );
                if (!mukkadam) return;
                const rate = mukkadam.activity_rates?.find((rt: any) =>
                  rt.activity_id === act.activity_id ||
                  rt.activity_name === act.activity_name
                );
                const confirmed = window.confirm(
                  `Allocate ${act.remaining_area} ac of "${act.activity_name}" to ${r.mukkadamName}?\n\n` +
                    `Workers: ${r.availableWorkers}  |  Rate: ₹${rate?.rate_per_acre || 0}/ac`
                );
                if (!confirmed) return;

                const enrichedAct = {
                  ...act,
                  __prefill: {
                    mukkadam_id: r.mukkadamId,
                    allocated_workers: r.availableWorkers,
                    allocated_area: Number(act.remaining_area),
                    mukkadam_rate: Number(rate?.rate_per_acre || 0),
                  },
                };
                onStartAllocation(job.job_id, act.id, enrichedAct);
                setOpen(false);
              };

              return (
                <button
                  key={i}
                  type="button"
                  onClick={handleTeamClick}
                  // disabled={!canDo}
                  className={`w-full flex items-center justify-between px-2 py-1 rounded text-xs text-left ${
                    canDo
                      ? 'hover:bg-teal-50 text-teal-800'
                      : 'text-gray-400 cursor-not-allowed'
                  }`}
                >
                  <span>{r.mukkadamName}</span>
                  <span
                    className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                      r.availableWorkers === 0
                        ? 'bg-gray-100 text-gray-400'
                        : canDo
                        ? 'bg-green-50 text-green-700'
                        : 'bg-red-50 text-red-600'
                    }`}
                  >
                    {r.availableWorkers === 0
                      ? '🏖️ Holiday'
                      : `${needed} needed / ${r.availableWorkers} avail`}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

const DayDetailModal: React.FC<DayDetailModalProps> = ({
  date,
  allocations,
  mukkadams,
  overloads,
  onLeavesUpdated,
  filters,
  allJobs,
  viewMode,
  capacitySummary,
  leaves,potentialJobs,
  onClose,
onAllocationDateChange,
  onAllocationDelete,
  jobs,onStartAllocation,clusterId
}) => {
const [activeTab, setActiveTab] =
  useState<'allocations' | 'jobs' | 'conflicts' | 'potential' | 'maxwork'|'Notes' | 'leaves'>(
    'jobs'
  );

function MoveJobButton({ job, act }: {
  job: any;
  act: any;
  
}) {const MOVE_REASONS = [
  'Not strict job — can reschedule',
  'Easy farmer — farmer agreed to move',
];

// Add to state:
const [moveReason, setMoveReason] = useState('');
  const [open, setOpen] = useState(false);
  const [moveDate, setMoveDate] = useState('');
  const [moveArea, setMoveArea] = useState<number>(Number(act.remaining_area));
  const [saving, setSaving] = useState(false);
const handleSubmit = async () => {
  if (!moveDate) { toast.error('Select a date'); return; }
  if (!moveArea || moveArea <= 0) { toast.error('Enter valid area'); return; }
  if (!moveReason.trim()) { toast.error('Please provide a reason'); return; }
  if (moveArea > Number(act.remaining_area)) { toast.error('Exceeds remaining area'); return; }
  const token = localStorage.getItem('auth_token')
  setSaving(true);
  try {
    const res = await fetch(`${API_BASE_URL}/api/job-activities/${act.id}/move/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json','Authorization': `Token ${token}`},
      body: JSON.stringify({ new_date: moveDate, area: moveArea, reason: moveReason }),
    });
    if (res.ok) {
      toast.success('Job moved');
      setOpen(false);
            // window.location.reload();
onLeavesUpdated();
      // onSuccess?.();
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



  return (
    <>
      <button
        onClick={() => setOpen(true)}
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
          <label className="text-xs font-semibold text-gray-600 block mb-1">Area to Move (ac)</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            max={act.remaining_area}
            value={moveArea}
            onChange={e => setMoveArea(parseFloat(e.target.value) || 0)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
          />
          <p className="text-xs text-gray-400 mt-1">Max: {act.remaining_area} ac (remaining)</p>
          {moveArea > Number(act.remaining_area) && (
            <p className="text-xs text-red-500 mt-1">⚠ Exceeds remaining area</p>
          )}
        </div>

        {/* Reason — quick select */}
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
          disabled={saving || !moveReason.trim() || moveArea > Number(act.remaining_area)}
          className="flex-1 px-4 py-2 bg-orange-500 text-white rounded-lg text-sm font-bold hover:bg-orange-600 disabled:opacity-50 transition"
        >
          {saving ? 'Moving...' : 'Confirm Move'}
        </button>
      </div>
    </div>
  </div>,
  document.body
)}
    </>
  );
}

  const [moveModal, setMoveModal] = useState<{
  allocation: AllocationWithReport;
  maxArea: number;
} | null>(null);
const [moveForm, setMoveForm] = useState({ date: '', area: '' });
const [moveLoading, setMoveLoading] = useState(false);

// STEP 2 — Add inside DayDetailModal component, near the top with other state:
const { user: currentUser } = useCurrentUser();
const currentUserId   = currentUser?.id   ?? 0;
const currentUserName = currentUser?.full_name ?? currentUser?.username ?? '';

const handleMoveSubmit = async () => {
  if (!moveModal) return;
  const area = parseFloat(moveForm.area);
  const token = localStorage.getItem('auth_token');
  
  if (!moveForm.date) return toast.error('Select a date');
  if (isNaN(area) || area <= 0) return toast.error('Enter valid area');
  if (area > moveModal.maxArea) return toast.error(`Area cannot exceed ${moveModal.maxArea} ac`);

  setMoveLoading(true);
  try {
    const res = await fetch(
      `${API_BASE_URL}/api/allocations/${moveModal.allocation.id}/change_date/?cluster_id=${clusterId}`,
      {
        method: 'POST',
        headers: {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Token ${token}` } : {}),
  },
        body: JSON.stringify({
          allocated_date: moveForm.date,
          allocated_area: area,
        }),
      }
    );
    const data = await res.json();
    if (!res.ok) {
      toast.error(data.error || 'Failed to move allocation');

      return;
    }
    toast.success('Allocation moved successfully');
    setMoveModal(null);
          onLeavesUpdated();
    setMoveForm({ date: '', area: '' });
    // onLeavesUpdated(); // refresh
  } catch {
    toast.error('Network error');
  } finally {
    setMoveLoading(false);
  }
};
const handleDeleteAllocation = async (allocationId: number) => {
  try {
    const token = localStorage.getItem('auth_token')
    const res = await fetch(`${API_BASE_URL}/api/allocations/${allocationId}/delete_allocation/`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json','Authorization': `Token ${token}` },
    });
    if (res.ok) {
      toast.success('✅ Allocation deleted and area restored.');
      onLeavesUpdated(); // reuse same refresh trigger
    } else {
      const result = await res.json();
      toast.error(result.message || 'Failed to delete allocation');
    }
  } catch {
    toast.error('Network error');
  }
};
  const dateStr = date.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  });
const [selectedMaxWorkActivity, setSelectedMaxWorkActivity] = useState<number | null>(null);

const isoDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

const jobsOnThisDay = jobs.filter(job =>
  job.activities?.some(act =>
    act.scheduled_date?.slice(0, 10) === isoDate
  )
);
// ── inside DayDetailModal, replace state declarations ────────────────────────
const [verifyLoading, setVerifyLoading] = useState<number | null>(null);
const [disputeModal, setDisputeModal] = useState<{
  allocationId: number;
  mukkadamName: string;
  activityName: string;
  actualArea: number;
} | null>(null);
const [disputeReason, setDisputeReason] = useState('');

// ── farmer verify handler ─────────────────────────────────────────────────────
const handleFarmerVerify = async (
  allocationId: number,
  agreed: boolean,
  disputeReasonText?: string
) => {
  setVerifyLoading(allocationId);
  try {
    const res = await fetch(`${API_BASE_URL}/api/farmer/verify-work/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        allocation_id: allocationId,
        agreed,
        dispute_reason: disputeReasonText || '',
      }),
    });
    const result = await res.json();
    if (res.ok) {
      toast.success(agreed
        ? '✅ Verified! Allocation adjusted automatically.'
        : '⚠️ Dispute recorded.'
      );
            onLeavesUpdated()
      // trigger parent refresh
      // if (onAllocationDelete) onAllocationDelete({ id: -1 } as any);
    } else {
      toast.error(result.error || 'Failed to verify');
    }
  } catch {
    toast.error('Network error');
  } finally {
    setVerifyLoading(null);
  }
};

// ── verification status helper ────────────────────────────────────────────────
const getVerifyStatus = (a: AllocationWithReport) => {
  if (!a.report_submitted) return 'not_submitted';
  if (a.farmer_agreed === null || a.farmer_agreed === undefined) return 'pending';
  if (a.farmer_agreed) return 'agreed';
  return 'disputed';
};

const VERIFY_STYLE = {
  not_submitted: { bg: '#f3f4f6', color: '#6b7280',  label: '⏳ No Report Yet' },
  pending:       { bg: '#fef9c3', color: '#b45309',  label: '👀 Awaiting Verification' },
  agreed:        { bg: '#dcfce7', color: '#16a34a',  label: '✅ Verified' },
  disputed:      { bg: '#fef2f2', color: '#dc2626',  label: '❌ Disputed' },
};
  // ✅ Filter allocations based on activity filter
const filteredAllocations = allocations.filter(alloc => {
  // If no activity filter, show all
  if (!filters?.activityId) return true;

  // ✅ Use allJobs instead of jobs for lookup
  const job = (allJobs || jobs).find(j => j.job_id === alloc.job_id);
  if (!job) return true; // Keep if we can't find job

  // Find the activity for this allocation
  const activity = job.activities?.find(a => a.id === alloc.job_activity);
  if (!activity) return true;

  // Check if activity matches filter
  return activity.activity_id === filters.activityId;
});


// map of mukkadamId -> has any half-day allocation on this date
const hasHalfDayByMukkadam = new Map<number, boolean>();

allocations.forEach((a: any) => {
  if (a.allocated_date?.slice(0, 10) !== isoDate) return;
  if (a.allows_second_job === true) {
    hasHalfDayByMukkadam.set(a.mukkadam, true);
  }
});



// ── State ─────────────────────────────────────────────────────────────────────
const [halfDayDialog, setHalfDayDialog] = useState<{
  open: boolean;
  jobId: string;
  act: any;
  mukkadam: any;
  rate: any;
  availableWorkers: number;
  neededWorkers: number;
  remainingArea: number;
  isSecondJob: boolean; 
  targetDate: string;  // ← ADD THIS
} | null>(null);


const { isAdmin, userData, logout: authLogout, isLoading } = useAuth();

const [allowsSecondJob, setAllowsSecondJob] = useState(false);

// ── Confirm handler (fires when user clicks "Allocate" in the dialog) ─────────
const handleConfirmHalfDay = async () => {
  if (!halfDayDialog) return;
  const { jobId, act, mukkadam, rate, availableWorkers, remainingArea } = halfDayDialog;

  const areaToAllocate = remainingArea;
  // const maxArea = availableWorkers * Number(rate?.productivity_per_worker || 0);
  // const isPartial = maxArea < remainingArea && maxArea > 0;
  // const finalArea = isPartial ? maxArea : areaToAllocate;
  const finalArea = areaToAllocate;
const token = localStorage.getItem('auth_token');
  try {
    const res = await fetch(`${API_BASE_URL}/api/allocations/create_allocation/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json',
        'Authorization': `Token ${token}`, },
      body: JSON.stringify({
        job_activity_id: act.id,
        mukkadam_id: mukkadam.mukkadam_id,
        allocated_date: isoDate,
        allocated_area: finalArea,
        allocated_workers: availableWorkers,
        farmer_rate: act.rate_per_acre,
        mukkadam_rate: Number(rate?.rate_per_acre || 0),
        cluster_id: clusterId,
        skip_strict_check: false,
        allows_second_job: halfDayDialog.isSecondJob ? false : allowsSecondJob,  // ← send flag
      }),
    });

    const data = await res.json();

    if (res.ok) {
      toast.success(
        allowsSecondJob
          ? `Allocated to ${mukkadam.mukkadam_name} (½ day — available for 1 more job)`
          : `Allocated to ${mukkadam.mukkadam_name}`
      );
      setHalfDayDialog(null);
      setAllowsSecondJob(false);
      onLeavesUpdated();
      
    } else {
      toast.error(data.error || 'Allocation failed');
    }
  } catch (e) {
    toast.error('Allocation failed');
    console.error(e);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
// PART C — Half-day confirm dialog JSX
// Place this ANYWHERE inside your DayDetailModal return(), e.g. just before
// the closing </div> of the modal.
// ══════════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════════
// PART D — CalendarCell: add ½ badge
// In your CalendarCell days.map() block, add this derived value and badge chip.
// ══════════════════════════════════════════════════════════════════════════════

// Add to DayDetailModal state
const [showEditAllocationModal, setShowEditAllocationModal] = useState(false);
const [editingAllocation, setEditingAllocation] = useState<Allocation | null>(null);
const [editForm, setEditForm] = useState({
  mukkadam_id: 0,
  allocated_date: '',
  allocated_workers: 0,
  allocated_area: 0,
  mukkadam_rate: 0,
});



const [showLeaveModal, setShowLeaveModal] = useState(false);
const [onLeavesUpdatedTrigger, setOnLeavesUpdatedTrigger] = useState(0); // To refresh internal UI if needed

// Inside DayDetailModal component
const [showExtraCrewModal, setShowExtraCrewModal] = useState(false);
const [selectedMukkadamForExtra, setSelectedMukkadamForExtra] = useState<Mukkadam | null>(null);
const [extraCrewCount, setExtraCrewCount] = useState(1);

const [maxCapacity, setMaxCapacity] = useState<number | null>(null);
const [availableWorkers, setAvailableWorkers] = useState<number | null>(null);


// Handle edit allocation
const handleEditAllocation = async () => {
  if (!editingAllocation) return;

  // Validate area
  if (maxCapacity !== null && editForm.allocated_area > maxCapacity) {
    toast.error(
      `Area (${editForm.allocated_area.toFixed(2)} ac) exceeds capacity (${maxCapacity.toFixed(2)} ac)`
    );
    return;
  }

  // Validate workers
  if (availableWorkers !== null && editForm.allocated_workers > availableWorkers) {
    toast.error(
      `Only ${availableWorkers} workers available on ${editForm.allocated_date}`
    );
    return;
  }

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/allocations/${editingAllocation.id}/update_allocation/?cluster_id=${clusterId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      toast.error(data.error || 'Failed to update allocation');
      return;
    }

    toast.success('Allocation updated successfully!');
    setShowEditAllocationModal(false);
    setEditingAllocation(null);
         
    onLeavesUpdated(); // Refresh allocations
  } catch (error) {
    toast.error('Failed to update allocation');
    console.error(error);
  }
};

const [availableMukkadamIds, setAvailableMukkadamIds] = useState<Set<number>>(new Set());

// // workers already allocated on this day, per mukkadam
// const usedWorkersByMukkadam = new Map<number, number>();

// allocations.forEach(a => {
//   const current = usedWorkersByMukkadam.get(a.mukkadam) || 0;
//   usedWorkersByMukkadam.set(a.mukkadam, current + (a.allocated_workers || 0));
// });



// ✅ NEW — skip allocations where allows_second_job is true:
const usedWorkersByMukkadam = new Map<number, number>();
allocations.forEach(a => {
  if ((a as any).allows_second_job === true) return;  // ← half-day, still free
  const current = usedWorkersByMukkadam.get(a.mukkadam) || 0;
  usedWorkersByMukkadam.set(a.mukkadam, current + (a.allocated_workers || 0));
});

const handleSaveExtraCrew = async () => {
  if (!selectedMukkadamForExtra) return;

  try {
    const res = await fetch(`${API_BASE_URL}/api/extra-workers/`, {
      method: 'POST', // As per your requirement
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mukkadam_id: selectedMukkadamForExtra.mukkadam_id,
        mukkadam: selectedMukkadamForExtra.mukkadam_id, // Double mapping as requested
        date: isoDate, // Your existing formatted date variable
        workers: extraCrewCount,
      }),
    });

    if (res.ok) {
      toast.success(`Successfully added workers`);
      setShowExtraCrewModal(false);
            // window.location.reload();
            onLeavesUpdated();
      // Trigger global refresh using the existing pattern
      if (onAllocationDelete) onAllocationDelete({ id: -1 } as any);
    } else {
      toast.error('Failed to add workers');
    }
  } catch (e) {
    console.error(e);
    toast.error('Network error');
  }
};
const maxWorkMap = new Map<string, MaxWorkRow>();

mukkadams.forEach((m) => {
  // ── AVAILABILITY GATE: trust the API ─────────────────────────
  if (!availableMukkadamIds.has(m.mukkadam_id)) return; // not available today
  // ─────────────────────────────────────────────────────────────

  const baseCrew = (m as any).available_crew_size ?? m.crew_size ?? 0;
  const used = usedWorkersByMukkadam.get(m.mukkadam_id) || 0;
  const remainingWorkers = Math.max(baseCrew - used, 0);

  (m.activity_rates || []).forEach((rate: any) => {
    const productivity = Number(rate.productivity_per_worker || 0);
    if (!productivity) return;

    const maxArea = remainingWorkers * productivity;
    const key = `${m.mukkadam_id}-${rate.activity_id}`;

    if (!maxWorkMap.has(key)) {
      maxWorkMap.set(key, {
        mukkadamId: m.mukkadam_id,
        mukkadamName: m.mukkadam_name,
        activityId: rate.activity_id,
        activityName: rate.activity_name,
        productivity,
        availableWorkers: remainingWorkers,
        maxArea,
      });
    }
  });
});
const maxWorkRows = Array.from(maxWorkMap.values());

// unique activities for the dropdown
const maxWorkActivities = [
  ...new Map(
    maxWorkRows.map(r => [r.activityId, { id: r.activityId, name: r.activityName }])
  ).values(),
];

// filter rows by selected activity
const visibleMaxWorkRows = selectedMaxWorkActivity
  ? maxWorkRows.filter(r => r.activityId === selectedMaxWorkActivity)
  : maxWorkRows;

// total capacity for the selected activity
const totalMaxArea = visibleMaxWorkRows.reduce((sum, r) => sum + r.maxArea, 0);

const modes = Array.isArray(viewMode) ? viewMode : [viewMode];
const isBothMode = modes.includes('jobs') && modes.includes('allocations');


{/* Summary bar like DayModal: acres + slots */}
const dayPlannedAc = jobsOnThisDay.reduce((sum, job) => {
  return (
    sum +
    (job.activities || []).reduce((s, act) => {
      if (act.scheduled_date?.slice(0, 10) !== isoDate) return s;
      return s + Number(act.total_area || 0);
    }, 0)
  );
}, 0);

const dayAllocatedAc = allocations.reduce(
  (s, a) => s + Number((a as any).allocated_area || 0),
  0,
);

// slots: used = same logic as calendar (allows_second_job 2/1 with cap 2 per (mukkadam,job))
// total = available teams * 2 using availableMukkadamIds you already fetch in DayDetailModal
const slotsByKey = new Map<string, any[]>();
allocations.forEach((a: any) => {
  const key = `${a.mukkadam}-${a.job_id}`;
  const arr = slotsByKey.get(key) || [];
  arr.push(a);
  slotsByKey.set(key, arr);
});

let usedSlotsSummary = 0;
slotsByKey.forEach((list) => {
  let slotsForJob = 0;
  list.forEach((a) => {
    const add = a.allows_second_job === true ? 1 : 2;
    slotsForJob += add;
  });
  if (slotsForJob > 2) slotsForJob = 2;
  usedSlotsSummary += slotsForJob;
});

const totalSlotsSummary = availableMukkadamIds.size * 2;
// acres still to do today
// needed: only jobs not yet fully allocated on this day
const neededAcToday = jobsOnThisDay.reduce((sum, job) => {
  return (
    sum +
    (job.activities || []).reduce((s, act: any) => {
      if (act.scheduled_date?.slice(0, 10) !== isoDate) return s;

      const total = Number(act.total_area || 0);
      const allocatedHere = allocations
        .filter(
          (a) =>
            a.job_id === job.job_id && a.job_activity === act.id,
        )
        .reduce(
          (x, a) => x + Number((a as any).allocated_area || 0),
          0,
        );

      const remainingForDay = Math.max(total - allocatedHere, 0);
      return s + remainingForDay;
    }, 0)
  );
}, 0);

// can-do: per mukkadam, remaining workers * best productivity,
// with 40% reduction if any half-day allocation
let canDoAcToday = 0;


const [noteJobId, setNoteJobId] = useState<string | null>(null);
    const [noteJobLabel, setNoteJobLabel] = useState('');
    const [dayNotes, setDayNotes] = useState<any[]>([]);
    const [notesLoading, setNotesLoading] = useState(false);
    const unresolvedNotesCount = dayNotes.filter(n => !n.is_resolved).length;


mukkadams.forEach((m: any) => {
  if (!availableMukkadamIds.has(m.mukkadam_id)) return;

  const baseCrew =
    (m as any).available_crew_size ?? m.crew_size ?? 0;
  const used = usedWorkersByMukkadam.get(m.mukkadam_id) || 0;
  const remainingWorkers = Math.max(baseCrew - used, 0);
  if (remainingWorkers <= 0) return;

  // best productivity across activities
  const bestProd = (m.activity_rates || []).reduce(
    (best: number, rate: any) => {
      const p = Number(rate.productivity_per_worker || 0);
      return p > best ? p : best;
    },
    0,
  );
  if (bestProd <= 0) return;

  // check if mukkadam has any half‑day allocation today
  const hasHalfDay = allocations.some(
    (a: any) =>
      a.mukkadam === m.mukkadam_id &&
      a.allocated_date?.slice(0, 10) === isoDate &&
      a.allows_second_job === true,
  );

  let maxAc = remainingWorkers * bestProd;

  // reduce capacity by 40% if doing any half-day job
  if (hasHalfDay) {
    maxAc = maxAc * 0.6; // 60% of full
  }

  canDoAcToday += maxAc;
});

useEffect(() => {
  // ── 1. Notes ──────────────────────────────────────────────────
  
    setNotesLoading(true);
    fetch(`${API_BASE_URL}/api/job-notes/?date=${isoDate}&cluster_id=${clusterId}`)
      .then(r => r.json())
      .then(data => setDayNotes(data))
      .finally(() => setNotesLoading(false));

      onLeavesUpdated();

  

  // ── 2. Available mukkadams for the day ────────────────────────
  const fetchAvailable = async () => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadams/daily_capacity_all/?date=${isoDate}&cluster_id=${clusterId}`
      );
      const data = await res.json();
      const ids = new Set<number>(
        (data as any[])
          .filter(d => d.available_crew_size > 0)
          .map(d => d.mukkadam_id)
      );
      setAvailableMukkadamIds(ids);
    } catch (e) {
      console.error('Failed to fetch daily capacity', e);
    }
  };
  fetchAvailable();

  // ── 3. Capacity for editing allocation ────────────────────────
  if (!editingAllocation || !editForm.mukkadam_id || !editForm.allocated_date) {
    setMaxCapacity(null);
    setAvailableWorkers(null);
    return;
  }

  const fetchCapacity = async () => {
    try {
      const mukkadam = mukkadams.find(m => m.mukkadam_id === editForm.mukkadam_id);
      if (!mukkadam) return;

      const res = await fetch(
        `${API_BASE_URL}/api/mukkadams/${editForm.mukkadam_id}/remaining_capacity/?date=${editForm.allocated_date}&cluster_id=${clusterId}`
      );
      const data = await res.json();
      const available = data.available_crew_size as number;

      const activity = (allJobs || jobs)
        .find(j => j.job_id === editingAllocation.job_id)
        ?.activities?.find(a => a.activity_name === editingAllocation.activity_name);

      if (!activity) return;

      const rate = mukkadam.activity_rates?.find(
        (r: any) =>
          r.activity_id === activity.activity_id ||
          r.activity_name === activity.activity_name
      );

      if (rate) {
        const productivity = Number(rate.productivity_per_worker);
        const maxArea = editForm.allocated_workers * productivity;

        setMaxCapacity(maxArea);
        setAvailableWorkers(available);

        setEditForm(prev => ({
          ...prev,
          mukkadam_rate: Number(rate.rate_per_acre),
        }));
      }
    } catch (error) {
      console.error('Failed to fetch capacity:', error);
    }
  };
  fetchCapacity();

}, [

  isoDate,
  clusterId,
  editingAllocation,
  editForm.mukkadam_id,
  editForm.allocated_date,
  editForm.allocated_workers,
]);

return (
  <div
    className="fixed inset-0 z-[99999] flex items-start justify-center pt-10"
    onClick={onClose}
  >
    <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />

    <div
      className="relative bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[85vh] flex flex-col overflow-hidden"
      onClick={(e) => e.stopPropagation()}
    >
      {/* Header */}
      <div className="px-6 pt-5 pb-3 border-b border-stone-100">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-stone-800">{dateStr}</h3>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs font-medium text-stone-500">
                Capacity:{' '}
                <span className="tabular-nums">
                  {capacitySummary.used}/{capacitySummary.total} workers
                </span>
              </span>
              {capacitySummary.conflicts?.length > 0 && (
                <>
                  <span className="text-stone-300 text-xs">·</span>
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600">
                    <AlertTriangle size={12} />
                    {capacitySummary.conflicts.length} conflicts
                  </span>
                </>
              )}
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-stone-100 text-stone-400"
          >
            <X size={18} />
          </button>
        </div>

<div className="mt-2 px-4 py-2 rounded-lg bg-stone-50 border border-stone-100">
  <div className="flex items-center justify-between">
    <span className="text-[11px] font-medium text-stone-500">
      Active workload
    </span>
    <span
      className={`text-[11px] font-bold tabular-nums ${
        neededAcToday > canDoAcToday ? 'text-red-600' : 'text-stone-700'
      }`}
    >
      {neededAcToday.toFixed(2)} / {canDoAcToday.toFixed(2)} ac
    </span>
  </div>

  {/* thinner bar, tight margin */}
  <div className="mt-1">
    <CapBar
      used={neededAcToday}
      total={canDoAcToday || 1}
      size="sm"
      showLabel={false}
    />
  </div>

  <div className="mt-1 flex items-center justify-between">
    <span className="text-[10px] text-stone-400">
      Slots: {usedSlotsSummary}/{totalSlotsSummary}
    </span>
    {neededAcToday > canDoAcToday && (
      <span className="text-[10px] text-red-500 font-medium flex items-center gap-1">
        <AlertTriangle size={9} /> Over by{' '}
        {(neededAcToday - canDoAcToday).toFixed(2)} ac
      </span>
    )}
  </div>
</div>


        {/* Tabs */}
        <div className="mt-3 flex gap-0 -mb-3">
          <button
            className={`px-4 py-2 text-xs sm:text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'allocations'
                ? 'border-emerald-600 text-emerald-700'
                : 'border-transparent text-stone-400 hover:text-stone-600'
            }`}
            onClick={() => setActiveTab('allocations')}
          >
            Allocations ({filteredAllocations.length})
          </button>

          <button
            className={`px-4 py-2 text-xs sm:text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'jobs'
                ? 'border-emerald-600 text-emerald-700'
                : 'border-transparent text-stone-400 hover:text-stone-600'
            }`}
            onClick={() => setActiveTab('jobs')}
          >
            Jobs (
            {jobsOnThisDay.reduce(
              (sum, job) =>
                sum +
                (job.activities?.filter(
                  (act) => act.scheduled_date?.slice(0, 10) === isoDate,
                ).length || 0),
              0,
            )}
            )
          </button>

          <button
            className={`px-4 py-2 text-xs sm:text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'maxwork'
                ? 'border-emerald-600 text-emerald-700'
                : 'border-transparent text-stone-400 hover:text-stone-600'
            }`}
            onClick={() => setActiveTab('maxwork')}
          >
            Max work
          </button>

          <button
            className={`px-4 py-2 text-xs sm:text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'leaves'
                ? 'border-emerald-600 text-emerald-700'
                : 'border-transparent text-stone-400 hover:text-stone-600'
            }`}
            onClick={() => setActiveTab('leaves')}
          >
            Attendance ({leaves.length})
          </button>

          <button
      className={`px-4 py-2 text-xs sm:text-sm font-medium border-b-2 transition-colors ${
        activeTab === 'Notes'
          ? 'border-indigo-600 text-indigo-700'
          : 'border-transparent text-stone-400 hover:text-stone-600'
      }`}
      onClick={() => setActiveTab('Notes')}
    >
      Notes {unresolvedNotesCount > 0 && (
        <span className="ml-1 px-1.5 py-0.5 bg-red-100 text-red-600 text-[10px] font-bold rounded-full">
          {unresolvedNotesCount}
        </span>
      )}
    </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-6 py-4 modal-body-scroll">

{/* ══════════════════════════════════════════════════════
    TAB 1 — ALLOCATIONS  (with day-end reports + verify)
══════════════════════════════════════════════════════ */}
{activeTab === 'allocations' && (
  <div className="tab-content">

    {/* Attendance alerts */}
    {leaves.length > 0 && (
      <div className="mb-4 space-y-2">
        <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">
          Attendance Alerts
        </div>
        {leaves.map(l => (
          <div
            key={l.id}
            className={`p-2 rounded border-l-4 ${
              l.leave_type === 'general'
                ? 'bg-blue-50 border-blue-400 text-blue-700'
                : 'bg-red-50 border-red-400 text-red-700'
            }`}
          >
            {l.leave_type === 'general'
              ? `🏖️ Holiday: ${l.reason}`
              : `👤 ${l.mukkadam_name}: ${l.crew_on_leave} workers absent`}
          </div>
        ))}
      </div>
    )}

    {/* ── Pending verification banner ── */}
    {(() => {
      const pendingCount = filteredAllocations.filter(
        a => (a as AllocationWithReport).report_submitted &&
             (a as AllocationWithReport).farmer_agreed == null
      ).length;
      const disputedCount = filteredAllocations.filter(
        a => (a as AllocationWithReport).farmer_agreed === false
      ).length;

      if (pendingCount === 0 && disputedCount === 0) return null;
      return (
        <div className="mb-4 flex gap-3">
          {pendingCount > 0 && (
            <div className="flex-1 flex items-center gap-2 bg-amber-50 border border-amber-300 rounded-xl px-4 py-2.5">
              <span className="text-amber-500 text-lg">👀</span>
              <div>
                <p className="text-xs font-bold text-amber-700">
                  {pendingCount} Allocation{pendingCount > 1 ? 's' : ''} Awaiting Your Verification
                </p>
                <p className="text-xs text-amber-600">
                  Mukkadam has submitted day-end report — please review and verify
                </p>
              </div>
            </div>
          )}
          {disputedCount > 0 && (
            <div className="flex-1 flex items-center gap-2 bg-red-50 border border-red-300 rounded-xl px-4 py-2.5">
              <span className="text-red-500 text-lg">❌</span>
              <div>
                <p className="text-xs font-bold text-red-700">
                  {disputedCount} Dispute{disputedCount > 1 ? 's' : ''} Recorded
                </p>
                <p className="text-xs text-red-600">
                  Resolve with mukkadam and update verified area
                </p>
              </div>
            </div>
          )}
        </div>
      );
    })()}

    <div className="form-divider mb-4">
      Allocations ({filteredAllocations.length})
    </div>

    {filteredAllocations.length === 0 ? (
      <p className="empty-text">No allocations for this day.</p>
    ) : (
      <div className="space-y-4">
        {filteredAllocations.map(rawAlloc => {
          const a = rawAlloc as AllocationWithReport;
          const m = mukkadams.find(mk => mk.mukkadam_id === a.mukkadam);
          const verifyStatus = getVerifyStatus(a);
          const vstyle = VERIFY_STYLE[verifyStatus];

          const areaDiff = a.actual_area_done != null
            ? Number(a.actual_area_done) - Number(a.allocated_area)
            : null;

          const durationMins =
            a.actual_start_time && a.actual_end_time
              ? Math.round(
                  (new Date(a.actual_end_time).getTime() -
                   new Date(a.actual_start_time).getTime()) / 60000
                )
              : null;


          const mukkadamHasHalfDay =
  hasHalfDayByMukkadam.get(a.mukkadam) === true;


          return (
            <div
              key={a.id}
              className="rounded-xl border overflow-hidden"
              style={{
                borderColor:
                  verifyStatus === 'disputed' ? '#fca5a5' :
                  verifyStatus === 'pending'  ? '#fde68a' :
                  verifyStatus === 'agreed'   ? '#86efac' : '#e5e7eb',
                background:
                  verifyStatus === 'disputed' ? '#fff5f5' :
                  verifyStatus === 'pending'  ? '#fffdf0' : '#fff',
              }}
            >
              {/* ── Card header ── */}
              <div className="px-4 py-3 flex items-start justify-between gap-3">
                <div className="flex-1">
<div className="flex items-center gap-2 flex-wrap">
  <span className="font-bold text-gray-900 text-sm">
    {a.activity_name}
  </span>

  {/* mukkadam-level ½‑day indicator: show on ALL jobs of this mukkadam today */}
  {mukkadamHasHalfDay && (
    <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[10px] font-bold rounded-full border border-emerald-200">
      ½ day
    </span>
  )}

  {a.is_carry_forward && (
    <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-[10px] font-bold rounded-full">
      🔄 Carry-forward
    </span>
  )}
  <span
    className="px-2 py-0.5 text-[10px] font-bold rounded-full"
    style={{ background: vstyle.bg, color: vstyle.color }}
  >
    {vstyle.label}
  </span>
</div>


                  <p className="text-xs text-gray-500 mt-0.5">
                    Team: <strong className="text-gray-700">{m?.mukkadam_name || 'N/A'}</strong>
                    Farmer: <strong className="text-gray-700">{a?.farmer_name || 'N/A'}</strong>
                    {/* Plot: <strong className="text-gray-700">{a?.plot_name || 'N/A'}</strong> */}
                    {' · '}Job{' '}
                    <span className="font-mono text-blue-600">#{a.job_id}</span>
                    {/* <span className="font-mono text-blue-600">#{a.farmer_name}</span> */}
                    
                  </p>
                  {a.notes && (
                    <p className="text-xs text-purple-600 mt-0.5 italic">{a.notes}</p>
                  )}
                </div>

                {/* Planned area pill */}
                <div className="text-right shrink-0">
  <p className="text-xs text-gray-400">Planned</p>
  <p className="font-bold text-gray-800">
    {Number(a.allocated_area).toFixed(2)} ac
  </p>
  <p className="text-xs text-gray-400">
    {a.allocated_workers} workers
  </p>
  {a.allows_second_job === true && (
    <p className="text-[10px] font-semibold text-emerald-600 mt-0.5">
      ½ day allocation
    </p>
  )}
</div>

              </div>

              {/* ── Planned vs Actual comparison ── */}
              {a.report_submitted && a.actual_area_done != null && (
                <div
                  className="mx-4 mb-3 rounded-xl overflow-hidden border"
                  style={{ borderColor: '#e5e7eb' }}
                >
                  <div
                    className="grid text-center text-xs"
                    style={{ gridTemplateColumns: '1fr 1fr 1fr' }}
                  >
                    {/* Planned */}
                    <div className="bg-blue-50 px-3 py-2.5 border-r border-gray-200">
                      <p className="text-[10px] font-bold text-blue-500 uppercase mb-1">
                        📋 Planned
                      </p>
                      <p className="font-bold text-gray-800 text-base">
                        {Number(a.allocated_area).toFixed(2)}
                        <span className="text-xs font-normal ml-0.5">ac</span>
                      </p>
                      <p className="text-gray-500 text-[11px]">
                        {a.allocated_workers} workers
                      </p>
                    </div>

                    {/* Actual */}
                    <div className="bg-green-50 px-3 py-2.5 border-r border-gray-200">
                      <p className="text-[10px] font-bold text-green-600 uppercase mb-1">
                        👷 Actual Done
                      </p>
                      <p
                        className="font-bold text-base"
                        style={{
                          color: areaDiff == null ? '#374151' :
                                 areaDiff < 0 ? '#dc2626' : '#16a34a'
                        }}
                      >
                        {Number(a.actual_area_done).toFixed(2)}
                        <span className="text-xs font-normal ml-0.5">ac</span>
                      </p>
                      <p className="text-gray-500 text-[11px]">
                        {a.actual_crew_size ?? a.allocated_workers} workers
                      </p>
                    </div>

                    {/* Variance */}
                    <div
                      className="px-3 py-2.5"
                      style={{
                        background: areaDiff == null ? '#f9fafb' :
                                    areaDiff < 0 ? '#fef2f2' :
                                    areaDiff > 0 ? '#f0fdf4' : '#f9fafb'
                      }}
                    >
                      <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">
                        Variance
                      </p>
                      {areaDiff != null ? (
                        <>
                          <p
                            className="font-bold text-base"
                            style={{ color: areaDiff < 0 ? '#dc2626' : areaDiff > 0 ? '#16a34a' : '#6b7280' }}
                          >
                            {areaDiff > 0 ? '+' : ''}{areaDiff.toFixed(2)}
                            <span className="text-xs font-normal ml-0.5">ac</span>
                          </p>
                          <p className="text-[11px]" style={{
                            color: areaDiff < 0 ? '#dc2626' : '#16a34a'
                          }}>
                            {areaDiff < 0
                              ? `${Math.abs(areaDiff).toFixed(2)} ac short`
                              : areaDiff > 0
                              ? `${areaDiff.toFixed(2)} ac extra`
                              : 'Exact match'}
                          </p>
                        </>
                      ) : (
                        <p className="text-gray-400 text-sm">—</p>
                      )}
                    </div>
                  </div>

                  {/* Time row */}
                  {(a.actual_start_time || a.actual_end_time) && (
                    <div className="bg-gray-50 border-t border-gray-200 px-3 py-2 flex items-center justify-between text-xs text-gray-500">
                      <span>
                        🕐 Start:{' '}
                        <strong>
                          {a.actual_start_time
                            ? new Date(a.actual_start_time).toLocaleTimeString('en-IN', {
                                hour: '2-digit', minute: '2-digit'
                              })
                            : '—'}
                        </strong>
                      </span>
                      {durationMins != null && (
                        <span className="px-2 py-0.5 bg-gray-200 rounded-full font-semibold">
                          {durationMins} mins
                        </span>
                      )}
                      <span>
                        🕐 End:{' '}
                        <strong>
                          {a.actual_end_time
                            ? new Date(a.actual_end_time).toLocaleTimeString('en-IN', {
                                hour: '2-digit', minute: '2-digit'
                              })
                            : '—'}
                        </strong>
                      </span>
                    </div>
                  )}

                  {/* Report submitted at */}
                  {a.report_submitted_at && (
                    <div className="bg-gray-50 border-t border-gray-100 px-3 py-1.5 text-[10px] text-gray-400">
                      Report submitted:{' '}
                      {new Date(a.report_submitted_at).toLocaleString('en-IN', {
                        dateStyle: 'short', timeStyle: 'short'
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* ── No report yet ── */}
              {!a.report_submitted && (
                <div className="mx-4 mb-3 px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-400 italic">
                  Mukkadam has not submitted day-end report yet
                </div>
              )}

              {/* ── Farmer response section ── */}
              {a.report_submitted && (
                <div className="mx-4 mb-4">
                  {verifyStatus === 'pending' && (
                    <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3">
                      <p className="text-xs font-bold text-amber-700 mb-1">
                        👀 Mukkadam reported{' '}
                        <strong>{Number(a.actual_area_done).toFixed(2)} ac</strong> done
                        {areaDiff != null && areaDiff !== 0 && (
                          <span
                            className="ml-1"
                            style={{ color: areaDiff < 0 ? '#dc2626' : '#16a34a' }}
                          >
                            ({areaDiff > 0 ? '+' : ''}{areaDiff.toFixed(2)} ac vs planned)
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-amber-600 mb-3">
                        {areaDiff != null && areaDiff < 0
                          ? `If you agree, ${Math.abs(areaDiff).toFixed(2)} ac will auto carry-forward to next working day`
                          : areaDiff != null && areaDiff > 0
                          ? `If you agree, next allocation will be reduced by ${areaDiff.toFixed(2)} ac`
                          : 'If you agree, settlement will use actual area done'}
      
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleFarmerVerify(a.id, true)}
                          disabled={verifyLoading === a.id}
                          className="flex-1 py-2 rounded-lg text-xs font-bold text-white transition"
                          style={{
                            background: verifyLoading === a.id ? '#86efac' : '#16a34a'
                          }}
                        >
                          {verifyLoading === a.id ? '...' : '✅ Agree & Auto-adjust'}
                        </button>
                        <button
                          onClick={() => {
                            setDisputeModal({
                              allocationId: a.id,
                              mukkadamName: m?.mukkadam_name || 'Mukkadam',
                              activityName: a.activity_name,
                              actualArea: Number(a.actual_area_done),
                            });
                            setDisputeReason('');
                          }}
                          disabled={verifyLoading === a.id}
                          className="flex-1 py-2 rounded-lg text-xs font-bold text-white bg-red-500 hover:bg-red-600 transition"
                        >
                          ❌ Dispute
                        </button>
                      </div>
                    </div>
                  )}

                  {verifyStatus === 'agreed' && (
                    <div className="rounded-xl border border-green-300 bg-green-50 px-4 py-2.5">
                      <p className="text-xs font-bold text-green-700">
                        ✅ You verified this report
                      </p>
                      <p className="text-xs text-green-600">
                        Settlement uses actual area:{' '}
                        <strong>{Number(a.actual_area_done).toFixed(2)} ac</strong>
                        {areaDiff != null && areaDiff < 0 && (
                          <span className="ml-1 text-green-500">
                            · {Math.abs(areaDiff).toFixed(2)} ac carried forward
                          </span>
                        )}
                      </p>
                      {a.farmer_response_at && (
                        <p className="text-[10px] text-green-400 mt-0.5">
                          {new Date(a.farmer_response_at).toLocaleString('en-IN', {
                            dateStyle: 'short', timeStyle: 'short'
                          })}
                        </p>
                      )}
                    </div>
                  )}

                  {verifyStatus === 'disputed' && (
                    <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-2.5">
                      <p className="text-xs font-bold text-red-700">❌ Disputed</p>
                      {a.farmer_dispute_reason && (
                        <p className="text-xs text-red-600 mt-1 bg-red-100 rounded-lg px-2 py-1">
                          "{a.farmer_dispute_reason}"
                        </p>
                      )}
                      <p className="text-[10px] text-red-400 mt-1">
                        Call mukkadam to resolve, then re-verify
                      </p>
                      {a.farmer_response_at && (
                        <p className="text-[10px] text-red-400">
                          Disputed on:{' '}
                          {new Date(a.farmer_response_at).toLocaleString('en-IN', {
                            dateStyle: 'short', timeStyle: 'short'
                          })}
                        </p>
                      )}
                      {/* Re-verify option after calling mukkadam */}
                      <button
                        onClick={() => {
                          setDisputeModal({
                            allocationId: a.id,
                            mukkadamName: m?.mukkadam_name || 'Mukkadam',
                            activityName: a.activity_name,
                            actualArea: Number(a.actual_area_done),
                          });
                          setDisputeReason('');
                        }}
                        className="mt-2 w-full py-1.5 rounded-lg text-[11px] font-bold text-red-600 border border-red-300 bg-white hover:bg-red-50 transition"
                      >
                        📞 Resolved? Update & Verify
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* ── Delete/Edit actions (bottom) ── */}
              {/* ── Delete/Edit actions (bottom) ── */}
<div className="px-4 pb-3 flex justify-end gap-2 border-t border-gray-100 pt-2">
  <button
    className="px-3 py-1.5 text-xs font-medium text-orange-600 hover:bg-orange-50 rounded-lg transition"
    onClick={() => setMoveModal({ allocation: a, maxArea: Number(a.allocated_area) })}
  >
    📅 Move
  </button>
{isAdmin &&(  <button
    className="px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg transition"
    onClick={() => {
      if (confirm(`Delete this allocation of ${Number(a.allocated_area).toFixed(2)} ac by ${m?.mukkadam_name || 'mukkadam'}? This will restore the area back to the activity.`)) {
        handleDeleteAllocation(a.id);
      }
    }}
  >
    🗑 Delete
  </button>) }
</div>
            </div>
          );
        })}
      </div>
    )}
  </div>
)}

{activeTab === 'Notes' && (
  <>
    {/* TEMP DEBUG — remove after fixing */}
    
    <NotesTabBody
      dayNotes={dayNotes}
      notesLoading={notesLoading}
      currentUserId={currentUserId}
      isoDate={isoDate}
      jobsOnThisDay={jobsOnThisDay}
      onOpenNoteForJob={(jobId, label) => {
        setNoteJobId(jobId);
        setNoteJobLabel(label);
      }}
    />
  </>
)}

{halfDayDialog?.open && ReactDOM.createPortal(
  <div
    style={{
      position: 'fixed', inset: 0, zIndex: 99999,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}
    onClick={() => { setHalfDayDialog(null); setAllowsSecondJob(false); }}
  >
    <div
      style={{
        background: '#fff', borderRadius: '16px', padding: '24px',
        width: '360px', boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
      }}
      onClick={e => e.stopPropagation()}
    >
      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#111827' }}>
          Confirm Allocation
        </h3>
        <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#6b7280' }}>
          {halfDayDialog.act.activity_name} → {halfDayDialog.mukkadam.mukkadam_name}
        </p>
      </div>

      {/* Summary rows */}
      <div style={{
        background: '#f9fafb', borderRadius: '10px', padding: '12px',
        fontSize: '0.8rem', color: '#374151', marginBottom: '16px',
        display: 'flex', flexDirection: 'column', gap: '6px',
      }}>
        {[
          ['Area', `${halfDayDialog.remainingArea.toFixed(2)} ac`],
          ['Workers available', `${halfDayDialog.availableWorkers} workers`],
          ['Workers needed', `${halfDayDialog.neededWorkers} workers`],
          ['Rate', `₹${Number(halfDayDialog.rate?.rate_per_acre || 0).toFixed(0)}/ac`],
        ].map(([label, value]) => (
          <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#6b7280' }}>{label}</span>
            <span style={{ fontWeight: 700 }}>{value}</span>
          </div>
        ))}
      </div>

      {halfDayDialog.isSecondJob ? (
  <div style={{
    display: 'flex', alignItems: 'flex-start', gap: '10px',
    padding: '12px', borderRadius: '10px',
    border: '2px solid #0ea5e9', background: '#f0f9ff', marginBottom: '16px',
  }}>
    <span style={{ fontSize: '1rem', flexShrink: 0 }}>½</span>
    <div>
      <p style={{ margin: 0, fontWeight: 700, fontSize: '0.82rem', color: '#0369a1' }}>
        2nd job — full day allocation
      </p>
      <p style={{ margin: '3px 0 0', fontSize: '0.72rem', color: '#0284c7', lineHeight: 1.5 }}>
        {halfDayDialog.mukkadam.mukkadam_name} already has a ½ day job today.
        This will be allocated as the 2nd job for the remaining half.
      </p>
    </div>
  </div>
) : (
  <label style={{
    display: 'flex', alignItems: 'flex-start', gap: '10px',
    padding: '12px', borderRadius: '10px', cursor: 'pointer',
    border: allowsSecondJob ? '2px solid #10b981' : '2px solid #e5e7eb',
    background: allowsSecondJob ? '#f0fdf4' : '#fff',
    marginBottom: '16px', transition: 'all 0.15s',
  }}>
    <input type="checkbox" checked={allowsSecondJob}
      onChange={e => setAllowsSecondJob(e.target.checked)}
      style={{ marginTop: '2px', accentColor: '#10b981', width: '16px', height: '16px', flexShrink: 0 }} />
    <div>
      <p style={{ margin: 0, fontWeight: 700, fontSize: '0.82rem', color: '#065f46' }}>
        ½ Can do 1 more job today
      </p>
      <p style={{ margin: '3px 0 0', fontSize: '0.72rem', color: '#6b7280', lineHeight: 1.5 }}>
        Workers stay available for a second job. This job runs in the first half of the day —
        worker count will <strong>not</strong> be deducted from daily capacity.
      </p>
    </div>
  </label>
)}

      {/* Buttons */}
      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
        <button
          type="button"
          onClick={() => { setHalfDayDialog(null); setAllowsSecondJob(false); }}
          style={{
            padding: '8px 18px', borderRadius: '8px',
            border: '1px solid #e5e7eb', background: '#fff',
            color: '#374151', fontSize: '0.82rem', cursor: 'pointer',
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleConfirmHalfDay}
          style={{
            padding: '8px 18px', borderRadius: '8px', border: 'none',
            background: allowsSecondJob ? '#10b981' : '#2563eb',
            color: '#fff', fontSize: '0.82rem', fontWeight: 700, cursor: 'pointer',
            transition: 'background 0.15s',
          }}
        >
          {allowsSecondJob ? '½ Allocate' : 'Allocate'}
        </button>
      </div>
    </div>
  </div>,
  document.body
)}


{/* ── Move Allocation Modal ── */}
{moveModal && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h3 className="font-bold text-gray-900 text-sm">📅 Move Allocation</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          {moveModal.allocation.activity_name} · {moveModal.allocation.farmer_name}
        </p>
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* Area */}
        <div>
          <label className="text-xs font-semibold text-gray-600 block mb-1">
            Area to move (max {moveModal.maxArea} ac)
          </label>
          <input
            type="number"
            step="0.01"
            max={moveModal.maxArea}
            value={moveForm.area}
            onChange={e => setMoveForm(f => ({ ...f, area: e.target.value }))}
            placeholder={`e.g. ${moveModal.maxArea}`}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
          />
          <p className="text-[10px] text-gray-400 mt-0.5">
            Current allocation: {moveModal.maxArea} ac
          </p>
        </div>

        {/* Date */}
        <div>
          <label className="text-xs font-semibold text-gray-600 block mb-1">
            Move to date
          </label>
          <input
            type="date"
            value={moveForm.date}
            // min={new Date().toISOString().slice(0, 10)}
            onChange={e => setMoveForm(f => ({ ...f, date: e.target.value }))}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
          />
        </div>
      </div>

      <div className="px-5 pb-4 flex gap-2">
        <button
          onClick={() => { setMoveModal(null); setMoveForm({ date: '', area: '' }); }}
          className="flex-1 py-2 rounded-lg text-xs font-semibold text-gray-600 border border-gray-200 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={handleMoveSubmit}
          disabled={moveLoading}
          className="flex-1 py-2 rounded-lg text-xs font-bold text-white bg-orange-500 hover:bg-orange-600 transition"
        >
          {moveLoading ? 'Moving...' : '📅 Confirm Move'}
        </button>
      </div>
    </div>
  </div>
)}
{/* ══════════════════════════════════════════════════════
    TAB 2 — JOBS (styled like the demo DayModal table)
══════════════════════════════════════════════════════ */}
{/* ══════════════════════════════════════════════════════
    TAB 2 — JOBS (DayModal style, acres-based)
══════════════════════════════════════════════════════ */}
{activeTab === 'jobs' && (
  <div className="flex-1">
    {jobsOnThisDay.length === 0 ? (
      <p className="text-sm text-stone-400 italic mt-4">
        No jobs scheduled.
      </p>
    ) : (
      <div className="mt-3 rounded-xl border border-stone-200 bg-white overflow-x-auto">
        <table className="w-full text-sm" style={{ minWidth: '880px' }}>
          <thead>
            <tr className="border-b border-stone-100 bg-stone-50/60">
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-stone-400 uppercase tracking-wider">
                Farmer
              </th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-stone-400 uppercase tracking-wider">
                Activity
              </th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-stone-400 uppercase tracking-wider">
                Status
              </th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-stone-400 uppercase tracking-wider">
                Team / Capacity
              </th>
              <th className="text-right px-4 py-2.5 text-xs font-semibold text-stone-400 uppercase tracking-wider">
                Action
              </th>
            </tr>
          </thead>

          <tbody>
            {jobsOnThisDay.flatMap((job) =>
              (job.activities || [])
                .filter((act) => {
                  if (act.scheduled_date?.slice(0, 10) !== isoDate)
                    return false;

                  const modes = Array.isArray(viewMode)
                    ? viewMode
                    : [viewMode];
                  const isManual =
                    (act as any).is_manually_moved === true;
                  const isBothMode =
                    modes.includes('jobs') &&
                    modes.includes('allocations');

                  if (isBothMode) return true;
                  if (
                    modes.includes('allocations') &&
                    !modes.includes('jobs')
                  ) {
                    return isManual;
                  }
                  return !isManual;
                })
                .map((act) => {
                  const workerRows = maxWorkRows.filter(
                    (r) => r.activityName === act.activity_name,
                  );

                  const actAllocations = filteredAllocations.filter(
  (al) => al.job_id === job.job_id && al.job_activity === act.id,
) as AllocationWithReport[];


const primaryAlloc = actAllocations[0];
const primaryMukkadamId = primaryAlloc?.mukkadam;

const mukkadamHasHalfDay =
  primaryMukkadamId != null &&
  hasHalfDayByMukkadam.get(primaryMukkadamId) === true;


                  const carryForwardAllocs = actAllocations.filter(
                    (al) => al.is_carry_forward,
                  );
                  const pendingVerify = actAllocations.filter(
                    (al) =>
                      al.report_submitted &&
                      al.farmer_agreed == null,
                  ).length;
                  const disputedCount = actAllocations.filter(
                    (al) => al.farmer_agreed === false,
                  ).length;

                  const totalActual = actAllocations
                    .filter((al) => al.actual_area_done != null)
                    .reduce(
                      (s, al) =>
                        s + Number(al.actual_area_done),
                      0,
                    );

                  const isAllocated =
                    Number(act.allocated_area) > 0;
                  const isFullyAllocated =
                    Number(act.allocated_area) >=
                    Number(act.total_area);

                  const rowBorder =
                    disputedCount > 0
                      ? '#fca5a5'
                      : pendingVerify > 0
                      ? '#fde68a'
                      : isFullyAllocated
                      ? '#86efac'
                      : isAllocated
                      ? '#fcd34d'
                      : '#e5e7eb';

                  const remainingArea = Number(
                    act.remaining_area ?? 0,
                  );

                  const modes = Array.isArray(viewMode)
                    ? viewMode
                    : [viewMode];
                  const isBothMode =
                    modes.includes('jobs') &&
                    modes.includes('allocations');

                  // total planned ac for display
                  const plannedTotal = Number(
                    act.total_area || 0,
                  );

                  return (
                    <tr
                      key={`${job.job_id}-${act.id}`}
                      className="border-b border-stone-50 hover:bg-stone-50/60 transition-colors"
                      style={{
                        borderLeft: `4px solid ${rowBorder}`,
                      }}
                    >
                      {/* Farmer + plot/crop/variety */}
                      <td className="px-4 py-3 align-top">
                        <p className="text-sm font-medium text-stone-700">
                          {job.farmer_name}
                        </p>
                        <p className="text-xs text-stone-400">
                          {(act as any).plot_name ||
                            (act as any).plot_code ||
                            job.plot_name ||
                            job.job_id}
                          {' · '}
                          {job.crop_name || '—'}
                          {job.variety
                            ? ` • ${job.variety}`
                            : ''}
                        </p>
                      </td>

                      {/* Activity + acres (like DayModal) */}
                      <td className="px-4 py-3 align-top">
                        <p className="text-sm text-stone-700">
                          {act.activity_name}
                        </p>
                        <p className="text-xs text-stone-500 font-semibold">
                          {plannedTotal.toFixed(2)} ac
                        </p>
                      </td>

                      {/* Status: AI/H, moved, CF, pending/disputed */}
                      <td className="px-4 py-3 align-top">
                        <div className="flex items-center gap-2 flex-wrap">
                          {(act as any).is_manually_moved &&
                            (act as any)
                              .original_scheduled_date && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-200">
                              ↩ from{' '}
                              {new Date(
                                (act as any)
                                  .original_scheduled_date,
                              ).toLocaleDateString('en-IN', {
                                day: 'numeric',
                                month: 'short',
                              })}
                            </span>
                          )}

                          {!(act as any).is_manually_moved &&
                            (act as any).moved_to_date && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-200">
                                ↪ to{' '}
                                {new Date(
                                  (act as any).moved_to_date,
                                ).toLocaleDateString('en-IN', {
                                  day: 'numeric',
                                  month: 'short',
                                })}
                              </span>
                            )}
                            

                          {(act as any).is_manually_moved ? (
                            <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded-md text-[10px] font-bold">
                              H
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 bg-sky-100 text-sky-700 rounded-md text-[10px] font-bold">
                              AI
                            </span>
                          )}

                          {carryForwardAllocs.length > 0 && (
                            <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 rounded-md text-[10px] font-bold">
                              🔄 CF
                            </span>
                          )}

                          
                        </div>

                        {(act as any).is_manually_moved &&
                          (act as any).move_reason && (
                            <div className="text-[11px] text-stone-500 mt-0.5">
                              Reason:{' '}
                              {(act as any).move_reason}
                            </div>
                          )}

                        <div className="flex gap-1 mt-1 flex-wrap">
                          {pendingVerify > 0 && (
                            <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded-md text-[10px] font-bold">
                              👀 {pendingVerify} pending
                            </span>
                          )}
                          {disputedCount > 0 && (
                            <span className="px-1.5 py-0.5 bg-red-100 text-red-600 rounded-md text-[10px] font-bold">
                              ❌ {disputedCount} disputed
                            </span>
                          )}
                          
                        </div>

                        
                      </td>

                      {/* Team / Capacity (needed ac / can do ac) */}
                      <td className="px-4 py-3 align-top">
                        {isBothMode && actAllocations.length > 0 ? (
                          <div className="space-y-1">
                            {actAllocations.map((al) => {
  const alMukkadam = mukkadams.find(
    (mk) => mk.mukkadam_id === al.mukkadam,
  );
  const vs = getVerifyStatus(al);
  const vstyle = VERIFY_STYLE[vs];
  const isHalfDay = (al as any).allows_second_job === true;

  return (
    <div
      key={al.id}
      className="flex items-center gap-2 text-xs"
    >
      <span className="font-medium text-stone-700">
        {alMukkadam?.mukkadam_name || 'N/A'}
      </span>
      <span className="text-stone-400 tabular-nums">
        {Number(al.allocated_area).toFixed(2)} ac
      </span>

     {/* activity-level ½ day info */}
{mukkadamHasHalfDay && (
  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold mt-1">
    ½ day job
  </span>
)}


      {al.is_carry_forward && (
        <span className="text-violet-500 text-[10px]">🔄</span>
      )}
      <span
        className="px-1.5 py-0.5 rounded-full text-[10px] font-bold"
        style={{ background: vstyle.bg, color: vstyle.color }}
      >
        {vstyle.label}
      </span>
    </div>
  );
})}

                          </div>
                        ) : workerRows.length === 0 ? (
                          <span className="text-xs text-stone-400 italic">
                            No team data
                          </span>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {workerRows.map((r, i) => {
                              const canDoAc = Number(
                                r.maxArea || 0,
                              );
                              const fits =
                                remainingArea >
                                  0 && canDoAc >= remainingArea;

                              const handleTeamClick =
                                () => {
                                  // if (!fits) return;
                                  const mukkadam =
                                    mukkadams.find(
                                      (mk) =>
                                        mk.mukkadam_id ===
                                        r.mukkadamId,
                                    );
                                  if (!mukkadam) return;
                                  const rate =
                                    mukkadam
                                      .activity_rates?.find(
                                        (rt: any) =>
                                          rt.activity_id ===
                                            act.activity_id ||
                                          rt.activity_name ===
                                            act.activity_name,
                                      );

                                  const alreadyHasHalfDay =
                                    allocations.some(
                                      (a) =>
                                        a.mukkadam ===
                                          r.mukkadamId &&
                                        (a as any)
                                          .allows_second_job ===
                                          true,
                                    );

                                  setHalfDayDialog({
                                    open: true,
                                    jobId: job.job_id,
                                    act,
                                    mukkadam,
                                    rate,
                                    availableWorkers:
                                      r.availableWorkers,
                                    neededWorkers: 0,
                                    remainingArea:
                                      remainingArea,
                                    isSecondJob:
                                      alreadyHasHalfDay,
                                    targetDate: isoDate,
                                  });
                                };

                              return (
                                <button
                                  key={i}
                                  type="button"
                                  onClick={handleTeamClick}
                                  // disabled={!fits}
                                  className={[
                                    'flex items-center gap-2 px-2 py-1 rounded-full text-xs border',
                                    fits
                                      ? 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                                      : 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100',
                                  ].join(' ')}
                                >
                                  <span className="font-medium">
                                    {r.mukkadamName}
                                  </span>
                                  <span
                                    className={[
                                      'px-1.5 py-0.5 rounded-full text-[10px] font-bold',
                                      canDoAc === 0
                                        ? 'bg-stone-100 text-stone-400'
                                        : fits
                                        ? 'bg-emerald-100 text-emerald-700'
                                        : 'bg-red-100 text-red-600',
                                    ].join(' ')}
                                  >
                                    {canDoAc === 0
                                      ? '🏖️ Holiday'
                                      : `${remainingArea.toFixed(
                                          2,
                                        )} needed / ${canDoAc.toFixed(
                                          2,
                                        )} can do`}
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </td>

                      {/* Action column (Move button for unallocated) */}
                      <td className="px-4 py-3 text-right align-top">
                        <div className="flex flex-col items-end gap-1">
                          {actAllocations.length === 0 && (
                            <MoveJobButton
                              job={job}
                              act={act}
                            />
                          )}

                          <button
      onClick={() => {
        setNoteJobId(job.job_id);
        setNoteJobLabel(`${act.activity_name} – ${job.farmer_name}`);
      }}
      className="p-1.5 rounded-lg hover:bg-indigo-50 text-indigo-400 hover:text-indigo-600 transition"
      title="Add note"
    >
      <Pencil size={13} />
    </button>
                        </div>
                      </td>
                    </tr>
                  );
                }),
            )}
          </tbody>
        </table>
      </div>
    )}
  </div>
)}
{noteJobId && (
      <JobNoteModal
        jobId={noteJobId}
        jobLabel={noteJobLabel}
        noteDate={isoDate}
        currentUserId={currentUserId}   // ← get from auth context or localStorage
        currentUserName={currentUserName}
        clusterId={clusterId}
        onClose={() => setNoteJobId(null)}
      />
    )}

{/* ── Dispute Modal ── */}
{disputeModal && ReactDOM.createPortal(
  <div
    className="fixed inset-0 flex items-center justify-center"
    style={{ background: 'rgba(0,0,0,0.5)', zIndex: 99999 }}
    onClick={() => setDisputeModal(null)}
  >
    <div
      className="bg-white rounded-2xl shadow-2xl p-6 w-96"
      onClick={e => e.stopPropagation()}
    >
      <h4 className="font-bold text-gray-900 mb-1">❌ Dispute Report</h4>
      <p className="text-xs text-gray-500 mb-4">
        {disputeModal.mukkadamName} reported{' '}
        <strong>{disputeModal.actualArea.toFixed(2)} ac</strong> for{' '}
        {disputeModal.activityName}
      </p>

      {/* Quick reasons */}
      <div className="space-y-2 mb-3">
        {[
          'Area done is less than reported',
          'Workers were fewer than reported',
          'Work quality not acceptable',
          'Wrong plot / activity reported',
        ].map(r => (
          <button
            key={r}
            onClick={() => setDisputeReason(r)}
            className={`w-full text-left px-3 py-2 rounded-lg border text-xs font-medium transition ${
              disputeReason === r
                ? 'bg-red-50 border-red-400 text-red-700'
                : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-red-300 hover:bg-red-50'
            }`}
          >
            {disputeReason === r ? '✓ ' : ''}{r}
          </button>
        ))}
      </div>

      <textarea
        value={disputeReason}
        onChange={e => setDisputeReason(e.target.value)}
        placeholder="Or describe the issue in detail..."
        rows={3}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-red-300 resize-none"
      />
      {!disputeReason.trim() && (
        <p className="text-xs text-red-400 mt-1">Reason is required to dispute</p>
      )}

      <div className="flex gap-2 mt-4">
        <button
          onClick={() => setDisputeModal(null)}
          className="flex-1 px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-200"
        >
          Cancel
        </button>
        <button
          onClick={() => {
            if (!disputeReason.trim()) return;
            handleFarmerVerify(disputeModal.allocationId, false, disputeReason);
            setDisputeModal(null);
          }}
          disabled={!disputeReason.trim() || verifyLoading === disputeModal.allocationId}
          className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg text-sm font-bold hover:bg-red-600 disabled:opacity-50 transition"
        >
          {verifyLoading === disputeModal.allocationId ? 'Saving...' : 'Submit Dispute'}
        </button>
      </div>
    </div>
  </div>,
  document.body
)}
  {/* TAB 3: CONFLICTS */}
  {activeTab === 'conflicts' && (
    <div className="tab-content">
      {capacitySummary.conflicts.length === 0 && overloads.length === 0 ? (
        <p className="empty-text">No conflicts detected.</p>
      ) : (
        <>
          {capacitySummary.conflicts.map((conflict, idx) => (
            <div key={`cap-${idx}`} className="conflict-row card-style warning">
              <AlertCircle size={16} color="#ef4444" />
              <div>
                <strong>{conflict.mukkadam}</strong>
                <p>
                  {conflict.type === 'overload'
                    ? `Overload: ${conflict.activity} (needed ${conflict.needed.toFixed(2)} ac, capacity ${conflict.available.toFixed(2)} ac)`
                    : conflict.message}
                </p>
              </div>
            </div>
          ))}

          {overloads
            .filter(o => o.overloaded)
            .map((o, idx) => (
              <div key={`ol-${idx}`} className="conflict-row card-style warning">
                <AlertCircle size={16} color="#f97316" />
                <div>
                  <strong>{o.activity_name}</strong>
                  <p>plot {o.plot_name} – {o.farmer_name}</p>
                  <p>
                    Remaining: {o.remaining_area} ac, capacity: {o.available_capacity_area} ac,
                    deficit: {o.deficit} ac {o.overloaded ? '(OVERLOADED)' : ''}
                  </p>
                </div>
              </div>
            ))}
        </>
      )}
    </div>
  )}

  {/* TAB 4: POTENTIAL */}
  {activeTab === 'potential' && (
    <div className="tab-content">
      {(!potentialJobs || potentialJobs.length === 0) ? (
        <p className="empty-text">No potential jobs.</p>
      ) : (
        <div className="section">
          <h3 className="section-title">
            Potential Jobs (remaining / not done)
          </h3>

          <div className="potential-grid">
            {potentialJobs.map(p => (
              <div
                key={`${p.jobId}-${p.activityId}-${p.plotId}`}
                className={`potential-card ${p.status === 'NONE' ? 'status-red' : 'status-yellow'}`}
              >
                <div className="potential-card-header">
                  <div className="activity-title">
                    {p.activityName}
                  </div>
                  <span className="status-pill">
                    {p.status === 'NONE' ? 'Not started' : 'Partially done'}
                  </span>
                </div>

                <div className="potential-meta">
                  <span className="meta-item">
                    <span className="meta-label">Farmer</span>
                    <span className="meta-value">{p.farmerName}</span>
                  </span>
                  <span className="meta-item">
                    <span className="meta-label">Plot</span>
                    <span className="meta-value">{p.plotName}</span>
                  </span>
                  <span className="meta-item">
                    <span className="meta-label">Crop</span>
                    <span className="meta-value">{p.cropName}</span>
                  </span>
                  <span className="meta-item">
                    <span className="meta-label">Variety</span>
                    <span className="meta-value">{p.variety}</span>
                  </span>
                </div>

                <div className="potential-stats">
                  <div className="stat">
                    <div className="stat-label">Unbooked area</div>
                    <div className="stat-value">
                      {p.unbookedArea} <span className="stat-unit">ac</span>
                    </div>
                  </div>
                  <div className="stat">
                    <div className="stat-label">Rate</div>
                    <div className="stat-value">
                      ₹{p.clusterRate}
                      <span className="stat-unit">/ac</span>
                    </div>
                  </div>
                  <div className="stat">
                    <div className="stat-label">Potential</div>
                    <div className="stat-value highlight">
                      ₹{p.potentialRevenue}
                    </div>
                  </div>
                </div>

                <div className="potential-footer">
                  <span className="job-id">Job: {p.jobId}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )}


{activeTab === 'maxwork' && (
  <div className="tab-content">
    <h3 className="section-title">Max work for this day</h3>

    {/* Filter */}
    <div className="maxwork-filters">
      <label className="flex items-center gap-2 text-sm text-gray-600">
        Activity:
        <select
          value={selectedMaxWorkActivity ?? ''}
          onChange={(e) =>
            setSelectedMaxWorkActivity(
              e.target.value ? Number(e.target.value) : null
            )
          }
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-300"
        >
          <option value="">All activities</option>
          {maxWorkActivities.map(a => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
      </label>
    </div>

    {visibleMaxWorkRows.length === 0 ? (
      <p className="text-sm text-gray-400 italic mt-4">No capacity for this selection.</p>
    ) : (
      <>
        {/* Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
          {visibleMaxWorkRows.map((row, idx) => (
            <div
              key={idx}
              className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"
            >
              {/* Card Header */}
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="font-semibold text-gray-900 text-sm">{row.mukkadamName}</p>
                  <span className="inline-block mt-1 px-2 py-0.5 bg-teal-50 text-teal-700 text-xs rounded-full font-medium">
                    {row.activityName}
                  </span>
                </div>
                <div className="text-right shrink-0 ml-2">
                  <p className="text-xs text-gray-400">Max area</p>
                  <p className="text-lg font-bold text-teal-600">{row.maxArea.toFixed(2)}</p>
                  <p className="text-xs text-gray-400">acres</p>
                </div>
              </div>

              {/* Card Body */}
              <div className="flex items-center justify-between text-xs text-gray-500 border-t border-gray-100 pt-2 mt-2">
                <span className="flex items-center gap-1">
                  <Users size={11} />
                  {row.availableWorkers} workers
                </span>
                <span className="text-gray-400">×</span>
                <span>{row.productivity.toFixed(2)} ac/worker</span>
              </div>
            </div>
          ))}
        </div>

        {/* Total — only when a specific activity is selected */}
        {selectedMaxWorkActivity !== null && (
          <div className="mt-4 flex items-center justify-end">
            <div className="bg-teal-50 border border-teal-200 rounded-xl px-5 py-3 flex items-center gap-3">
              <span className="text-sm text-teal-700 font-medium">Total possible area</span>
              <span className="text-xl font-bold text-teal-600">{totalMaxArea.toFixed(2)} ac</span>
            </div>
          </div>
        )}
      </>
    )}
  </div>
)}

{/* TAB 6: ATTENDANCE & ADJUSTMENTS */}
{/* TAB: ATTENDANCE */}
{activeTab === 'leaves' && (
  <div className="tab-content">
    <div className="flex justify-between items-center mb-4">
      <h3 className="section-title">Attendance & Daily Adjustments</h3>
      <div className="flex gap-2">
        <button className="btn-secondary text-xs" onClick={() => setShowLeaveModal(true)}>
          <X size={14} /> Mark Absence
        </button>
        <button className="btn-primary text-xs" onClick={() => setShowExtraCrewModal(true)}>
          <Plus size={14} /> Add Extra Crew
        </button>
      </div>
    </div>

    {/* List existing adjustments (Leaves/Absences) */}
    <div className="space-y-2">
      {leaves.map(l => (
        <div key={l.id} className="attendance-row card-style" onClick={() => setShowLeaveModal(true)}>
          <span>{l.leave_type === 'general' ? '🏖️ Holiday' : `👤 ${l.mukkadam_name}`}</span>
          <span className="text-red-600">-{l.crew_on_leave} workers</span>
        </div>
      ))}
    </div>
  </div>
)}

{/* Add Extra Crew Modal Popup */}
{showExtraCrewModal && (
  <div className="modal-overlay" style={{ zIndex: 1100 }}>
    <div className="modal-content modal-sm">
      <div className="modal-header">
        <h3 className="modal-title">Add Extra Workers</h3>
        <button onClick={() => setShowExtraCrewModal(false)}><X size={20}/></button>
      </div>
      <div className="modal-body space-y-4">
        <div>
          <label className="form-label">Select Mukkadam</label>
          <select 
            className="form-select"
            onChange={(e) => setSelectedMukkadamForExtra(mukkadams.find(m => m.mukkadam_id === Number(e.target.value)) || null)}
          >
            <option value="">Choose Team...</option>
            {mukkadams.map(m => (
              <option key={m.mukkadam_id} value={m.mukkadam_id}>{m.mukkadam_name}  {m.crew_size}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="form-label">Extra Workers to Add</label>
          <input 
            type="number" 
            className="form-input" 
            value={extraCrewCount} 
            onChange={(e) => setExtraCrewCount(Number(e.target.value))}
          />
        </div>
      </div>
      <div className="modal-footer">
        <button className="btn-primary w-full" onClick={handleSaveExtraCrew}>Add Workers for Today</button>
      </div>
    </div>
  </div>
)}
{showLeaveModal && (
        <LeaveModal
          selectedDate={date} // Uses the 'date' prop passed into DayDetailModal
          mukkadams={mukkadams}
          existingLeaves={leaves} // Pass the same leaves prop
          onClose={() => setShowLeaveModal(false)}
          onLeaveMarked={() => {
            setShowLeaveModal(false);
            // This is important: it should call the refresh logic 
            // provided by the parent (CalendarPanel)
            // if (onAllocationDelete) onAllocationDelete({ id: -1 } as any); 
          }}
          clusterId={clusterId} 
        />
      )}
</div>
      </div>
    </div>
  );
};
export default DayDetailModal;