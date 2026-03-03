// components/DayDetailModal.tsx
import React, { useEffect } from 'react';
import { X,Plus,Users } from 'lucide-react';
import { Allocation, Job, Mukkadam } from '../types/types';
import './Day.css';
import { Tractor, User, AlertCircle } from 'lucide-react';
import { useState } from 'react';
// import { toast } from './ui/sonner';
import { toast } from './ui/sonner';
import { API_BASE_URL } from '@/types/config';
type PotentialStatus = 'PARTIAL' | 'NONE';
import { createPortal } from "react-dom";

import LeaveModal from './leave'; // Import your leave modal component
import ReactDOM from 'react-dom';
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

  setSaving(true);
  try {
    const res = await fetch(`${API_BASE_URL}/api/job-activities/${act.id}/move/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_date: moveDate, area: moveArea, reason: moveReason }),
    });
    if (res.ok) {
      toast.success('Job moved');
      setOpen(false);
            window.location.reload();

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
                if (!canDo) return;
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
                  disabled={!canDo}
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
  useState<'allocations' | 'jobs' | 'conflicts' | 'potential' | 'maxwork'| 'leaves'>(
    'jobs'
  );


  const [moveModal, setMoveModal] = useState<{
  allocation: AllocationWithReport;
  maxArea: number;
} | null>(null);
const [moveForm, setMoveForm] = useState({ date: '', area: '' });
const [moveLoading, setMoveLoading] = useState(false);

const handleMoveSubmit = async () => {
  if (!moveModal) return;
  const area = parseFloat(moveForm.area);
  
  if (!moveForm.date) return toast.error('Select a date');
  if (isNaN(area) || area <= 0) return toast.error('Enter valid area');
  if (area > moveModal.maxArea) return toast.error(`Area cannot exceed ${moveModal.maxArea} ac`);

  setMoveLoading(true);
  try {
    const res = await fetch(
      `${API_BASE_URL}/api/allocations/${moveModal.allocation.id}/change_date/?cluster_id=${clusterId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
          window.location.reload();
    setMoveForm({ date: '', area: '' });
    // onLeavesUpdated(); // refresh
  } catch {
    toast.error('Network error');
  } finally {
    setMoveLoading(false);
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
            window.location.reload();
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

// Fetch capacity when mukkadam or date changes
useEffect(() => {
  if (!editingAllocation || !editForm.mukkadam_id || !editForm.allocated_date) {
    setMaxCapacity(null);
    setAvailableWorkers(null);
    return;
  }
// Add this handler inside DayDetailModal component

  const fetchCapacity = async () => {
    try {
      const mukkadam = mukkadams.find(m => m.mukkadam_id === editForm.mukkadam_id);
      if (!mukkadam) return;

      // Get remaining capacity
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadams/${editForm.mukkadam_id}/remaining_capacity/?date=${editForm.allocated_date}&cluster_id=${clusterId}`
      );
      const data = await res.json();
      const available = data.available_crew_size as number;

      // Get productivity for this activity
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
        
        // Auto-update mukkadam rate
        setEditForm(prev => ({
          ...prev,
          mukkadam_rate: Number(rate.rate_per_acre)
        }));
      }
    } catch (error) {
      console.error('Failed to fetch capacity:', error);
    }
  };

  fetchCapacity();
}, [editForm.mukkadam_id, editForm.allocated_date, editForm.allocated_workers, editingAllocation]);

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
          window.location.reload();
    // onLeavesUpdated(); // Refresh allocations
  } catch (error) {
    toast.error('Failed to update allocation');
    console.error(error);
  }
};

const [availableMukkadamIds, setAvailableMukkadamIds] = useState<Set<number>>(new Set());

// Add this handler inside DayDetailModal component
const handleQuickAllocate = async (job: Job, activity: any) => {
  if (!activity) return;

  const mukkadam = mukkadams.find(m =>
    m.activity_rates?.some((r: any) =>
      r.activity_id === activity.activity_id ||
      r.activity_name === activity.activity_name
    )
  );

  if (!mukkadam) {
    toast.error('No mukkadam found with rate card for this activity');
    return;
  }

  const rate = mukkadam.activity_rates?.find((r: any) =>
    r.activity_id === activity.activity_id ||
    r.activity_name === activity.activity_name
  );

  const productivity = Number(rate?.productivity_per_worker || 0);
  const remainingArea = Number(activity.remaining_area || 0);

  if (!productivity || !remainingArea) {
    toast.error('Cannot calculate allocation. Check productivity and remaining area.');
    return;
  }

  const usedWorkers = usedWorkersByMukkadam.get(mukkadam.mukkadam_id) || 0;
  const availableWorkers = Math.max((mukkadam.crew_size || 0) - usedWorkers, 0);

  if (availableWorkers === 0) {
    toast.error(`No workers available today for ${mukkadam.mukkadam_name}`);
    return;
  }

  

  // ✅ Allocate whatever is possible today
  const maxAreaToday = parseFloat((availableWorkers * productivity).toFixed(2));
  const areaToAllocate = parseFloat(Math.min(maxAreaToday, remainingArea).toFixed(2));
  const workersNeeded = Math.ceil(areaToAllocate / productivity);
  const workers = Math.min(workersNeeded, availableWorkers);

  const isPartial = areaToAllocate < remainingArea;

  try {
    const res = await fetch(`${API_BASE_URL}/api/allocations/create_allocation/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_activity_id: activity.id,
        mukkadam_id: mukkadam.mukkadam_id,
        allocated_date: isoDate,
        allocated_area: areaToAllocate,  // ✅ what's possible, not full area
        allocated_workers: workers,
        farmer_rate: activity.rate_per_acre,
        mukkadam_rate: Number(rate?.rate_per_acre || 0),
        cluster_id: clusterId,
        skip_strict_check: false,
      }),
    });

    const data = await res.json();

    if (res.ok) {
      if (isPartial) {
        toast.success(
          `Partially allocated ${areaToAllocate} ac of ${remainingArea} ac ` +
          `to ${mukkadam.mukkadam_name}. ${(remainingArea - areaToAllocate).toFixed(2)} ac remaining for another date.`
        );
              window.location.reload();
      } else {
        toast.success(`Fully allocated ${areaToAllocate} ac to ${mukkadam.mukkadam_name}`);
              window.location.reload();
      }
      // onAllocationDelete({ id: -1 } as any);
    } else {
      toast.error(data.error || 'Allocation failed');
    }
  } catch (e) {
    toast.error('Allocation failed');
    console.error(e);
  }
};

useEffect(() => {
  const fetchAvailable = async () => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadams/daily_capacity_all/?date=${isoDate}&cluster_id=${clusterId}`
      );
      const data = await res.json();
      // data = [{mukkadam_id: 1, available_crew_size: 24}, ...]
      // Only keep mukkadams with available_crew_size > 0
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
}, [isoDate, clusterId]);
// workers already allocated on this day, per mukkadam
const usedWorkersByMukkadam = new Map<number, number>();

allocations.forEach(a => {
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
            window.location.reload();
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

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content day-detail-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3 className="modal-title">{dateStr}</h3>
            <p className="modal-subtitle">Capacity: {capacitySummary.used}/{capacitySummary.total} workers</p>
          </div>
          <button onClick={onClose} className="modal-close"><X size={20} /></button>
        </div>

<div className="modal-tabs">
  <button
    className={`modal-tab ${activeTab === 'allocations' ? 'active' : ''}`}
    onClick={() => setActiveTab('allocations')}
  >
    Allocations ({filteredAllocations.length})
  </button>

  <button
    className={`modal-tab ${activeTab === 'jobs' ? 'active' : ''}`}
    onClick={() => setActiveTab('jobs')}
  >
    Jobs ({jobsOnThisDay.reduce((sum, job) => 
    sum + (job.activities?.filter(act => 
      act.scheduled_date?.slice(0, 10) === isoDate
    ).length || 0), 0
  )})
  </button>

  {/* <button
    className={`modal-tab ${activeTab === 'conflicts' ? 'active' : ''}`}
    onClick={() => setActiveTab('conflicts')}
  >
    Conflicts ({
      capacitySummary.conflicts.length +
      overloads.filter((o: any) => o.overloaded).length
    })
  </button> */}

  {/* <button
    className={`modal-tab ${activeTab === 'potential' ? 'active' : ''}`}
    onClick={() => setActiveTab('potential')}
  >
    Potential ({potentialJobs ? potentialJobs.length : 0})
  </button> */}
  <button
    className={`modal-tab ${activeTab === 'maxwork' ? 'active' : ''}`}
    onClick={() => setActiveTab('maxwork')}
  >
    Max work
  </button>

<button
  className={`modal-tab ${activeTab === 'leaves' ? 'active' : ''}`}
  onClick={() => setActiveTab('leaves')}
>
  Attendance ({leaves.length})
</button>
</div>

<div className="modal-body-scroll">


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
              <div className="px-4 pb-3 flex justify-end gap-2 border-t border-gray-100 pt-2">
                {/* <button
                  className="px-3 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition"
                  onClick={() => {
                    setEditingAllocation(a);
                    setEditForm({
                      mukkadam_id: a.mukkadam,
                      allocated_date: a.allocated_date,
                      allocated_workers: a.allocated_workers,
                      allocated_area: a.allocated_area,
                      mukkadam_rate: a.mukkadam_rate,
                    });
                    setShowEditAllocationModal(true);
                  }}
                >
                  Edit
                </button> */}
                  <button
    className="px-3 py-1.5 text-xs font-medium text-orange-600 hover:bg-orange-50 rounded-lg transition"
    onClick={() => setMoveModal({ allocation: a, maxArea: Number(a.allocated_area) })}
  >
    📅 Move
  </button>
                {/* <button
                  className="px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg transition"
                  onClick={() => onAllocationDelete(a)}
                >
                  Remove
                </button> */}
              </div>
            </div>
          );
        })}
      </div>
    )}
  </div>
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
    TAB 2 — JOBS  (with inline allocation status + carry-forward indicator)
══════════════════════════════════════════════════════ */}
{activeTab === 'jobs' && (
  <div className="tab-content">
    {jobsOnThisDay.length === 0 ? (
      <p className="text-sm text-gray-400 italic mt-4">No jobs scheduled.</p>
    ) : (
      <div className="mt-2 rounded-xl border border-gray-200 overflow-x-auto">
        <table className="text-sm" style={{ minWidth: '820px', width: '100%' }}>
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500">Farmer</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500">Plot / Crop</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500">Activity</th>
              <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500">Planned</th>
              <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500">Actual</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500">Team / Status</th>
              {(() => {
  const modes = Array.isArray(viewMode) ? viewMode : [viewMode];
  const isBothMode = modes.includes('jobs') && modes.includes('allocations');
  return (isBothMode || modes.includes('allocations'))
    ? <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-500">Action</th>
    : null;
})()}
            </tr>
          </thead>
          <tbody>
            {(() => {
              const today = new Date();
              today.setHours(0, 0, 0, 0);
              const isPastDay = date < today;

              return jobsOnThisDay.flatMap(job =>
                job.activities
                  .filter(act => {
                    if (act.scheduled_date?.slice(0, 10) !== isoDate) return false;
                    
                    const modes = Array.isArray(viewMode) ? viewMode : [viewMode];
                    const isManual = (act as any).is_manually_moved === true;
                    
                    const isBothMode = modes.includes('jobs') && modes.includes('allocations');
                    
                    if (isBothMode) return true;                                          // ✅ Both → show all
                    if (modes.includes('allocations') && !modes.includes('jobs')) return isManual;  // Allocations only → manual only
                    return !isManual;                                                     // Jobs only → AI only
                  })
                  .map(act => {
                    const workerRows = maxWorkRows.filter(r => r.activityName === act.activity_name);

                    // Find all allocations for this activity today
                    const actAllocations = filteredAllocations.filter(
                      al => al.job_id === job.job_id && al.job_activity === act.id
                    ) as AllocationWithReport[];

                    const carryForwardAllocs = actAllocations.filter(al => al.is_carry_forward);
                    const normalAllocs = actAllocations.filter(al => !al.is_carry_forward);

                    // Verification summary across all allocations
                    const pendingVerify = actAllocations.filter(
                      al => al.report_submitted && al.farmer_agreed == null
                    ).length;
                    const disputedCount = actAllocations.filter(
                      al => al.farmer_agreed === false
                    ).length;

                    // Total actual done today
                    const totalActual = actAllocations
                      .filter(al => al.actual_area_done != null)
                      .reduce((s, al) => s + Number(al.actual_area_done), 0);

                    const isAllocated = Number(act.allocated_area) > 0;
                    const isFullyAllocated =
                      Number(act.allocated_area) >= Number(act.total_area);

                    // Row border color
                    const rowBorder =
                      disputedCount > 0 ? '#fca5a5' :
                      pendingVerify > 0 ? '#fde68a' :
                      isFullyAllocated ? '#86efac' :
                      isAllocated ? '#fcd34d' : '#e5e7eb';

                    return (
                      <tr
                        key={`${job.job_id}-${act.id}`}
                        className="border-b border-gray-100 hover:bg-gray-50 transition"
                        style={{ borderLeft: `4px solid ${rowBorder}` }}
                      >
                        {/* Farmer */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            <User size={13} className="text-gray-400 shrink-0" />
                            <span className="font-medium text-gray-800">{job.farmer_name}</span>
                          </div>
                        </td>

                        {/* Plot / Crop */}
                        <td className="px-4 py-3">
                          <p className="text-gray-700 font-medium">{job.plot_name || job.job_id}</p>
                          <p className="text-xs text-gray-400">
                            {job.crop_name || '—'}
                            {job.variety ? ` • ${job.variety}` : ''}
                          </p>
                        </td>

                        {/* Activity */}
                        <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
  <span className="font-medium">{act.activity_name}</span>

  {/* New copy (on new date) */}
  {act.is_manually_moved && act.moved_from_activity && act.original_scheduled_date && (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700">
       from {act.original_scheduled_date} → {act.scheduled_date}
    </span>
  )}

  {/* {!act.is_manually_moved &&(
    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700">
       from {act.original_scheduled_date} → {act.scheduled_date}
    </span>
  )} */}

  {/* Old copy (shrunk original) – if you ever mark it */}
  {/* {!act.is_manually_moved && !act.moved_from_activity && act.original_scheduled_date && (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-700">
      Part moved from {act.original_scheduled_date} to another date
    </span>
  )} */}

  {(act as any).is_manually_moved ? (
    <span className="px-1.5 py-0.5 bg-orange-100 text-orange-600 rounded text-[10px] font-bold">
      H
    </span>
  ) : (
    <span className="px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded text-[10px] font-bold">
      AI
    </span>
  )}
  {carryForwardAllocs.length > 0 && (
    <span className="px-1.5 py-0.5 bg-purple-100 text-purple-600 rounded text-[10px] font-bold">
      🔄 CF
    </span>
  )}
</div>

{act.is_manually_moved && act.move_reason && (
  <div className="text-[11px] text-gray-500 mt-0.5">
    Reason: {act.move_reason}
  </div>
)}

                          {/* Verification status badges */}
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {pendingVerify > 0 && (
                              <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded text-[10px] font-bold">
                                👀 {pendingVerify} pending
                              </span>
                            )}
                            {disputedCount > 0 && (
                              <span className="px-1.5 py-0.5 bg-red-100 text-red-600 rounded text-[10px] font-bold">
                                ❌ {disputedCount} disputed
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Planned area */}
                        <td className="px-4 py-3 text-right">
                          <p className="font-semibold text-gray-800">
                            {Number(act.allocated_area).toFixed(2)}
                            <span className="text-xs text-gray-400 ml-0.5">ac</span>
                          </p>
                          <p className="text-xs text-gray-400">
                            of {Number(act.total_area).toFixed(2)} ac
                          </p>
                          {Number(act.remaining_area) > 0.01 && (
                            <p className="text-xs text-amber-600 font-medium">
                              {Number(act.remaining_area).toFixed(2)} remaining
                            </p>
                          )}
                        </td>

                        {/* Actual done */}
                        <td className="px-4 py-3 text-right">
                          {totalActual > 0 ? (
                            <>
                              <p
                                className="font-bold"
                                style={{
                                  color: totalActual < Number(act.allocated_area)
                                    ? '#dc2626'
                                    : totalActual > Number(act.allocated_area)
                                    ? '#16a34a'
                                    : '#374151'
                                }}
                              >
                                {totalActual.toFixed(2)}
                                <span className="text-xs font-normal ml-0.5">ac</span>
                              </p>
                              <p
                                className="text-xs"
                                style={{
                                  color: totalActual < Number(act.allocated_area)
                                    ? '#dc2626' : '#16a34a'
                                }}
                              >
                                {(totalActual - Number(act.allocated_area) > 0 ? '+' : '')}
                                {(totalActual - Number(act.allocated_area)).toFixed(2)} ac
                              </p>
                            </>
                          ) : (
                            <span className="text-xs text-gray-300">—</span>
                          )}
                        </td>

                        {/* Team + status */}
{isBothMode && (
  <td className="px-4 py-3">
    {actAllocations.length > 0 ? (
      // existing allocated block (no change)
      <div className="space-y-1">
        {actAllocations.map(al => {
          const alMukkadam = mukkadams.find(mk => mk.mukkadam_id === al.mukkadam);
          const vs = getVerifyStatus(al);
          const vstyle = VERIFY_STYLE[vs];
          return (
            <div
              key={al.id}
              className="flex items-center gap-2 text-xs"
            >
              <span className="font-medium text-gray-700">
                {alMukkadam?.mukkadam_name || 'N/A'}
              </span>
              <span className="text-gray-400">
                {Number(al.allocated_area).toFixed(2)} ac
              </span>
              {al.is_carry_forward && (
                <span className="text-purple-500 text-[10px]">🔄</span>
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
      <span className="text-xs text-gray-400 italic">No team data</span>
    ) : (
      <div className="flex flex-wrap gap-2">
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
            if (!canDo) return;
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
          };

          return (
            <button
              key={i}
              type="button"
              onClick={handleTeamClick}
              disabled={!canDo}
              className={`flex items-center gap-2 px-2 py-1 rounded-full text-xs border ${
                canDo
                  ? 'border-teal-200 bg-teal-50 text-teal-800 hover:bg-teal-100'
                  : 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed'
              }`}
            >
              <span className="font-medium">{r.mukkadamName}</span>
              <span
                className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                  r.availableWorkers === 0
                    ? 'bg-gray-100 text-gray-400'
                    : canDo
                    ? 'bg-green-100 text-green-700'
                    : 'bg-red-100 text-red-600'
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
    )}
  </td>
)}


                        {/* Action column */}
                        {(() => {
  const modes = Array.isArray(viewMode) ? viewMode : [viewMode];
  const isBothMode = modes.includes('jobs') && modes.includes('allocations');
  if (!isBothMode) return null;

  const isAllocated = actAllocations.length > 0;

  return (
    <td className="px-4 py-3 text-center">
      {isAllocated ? null : <MoveJobButton job={job} act={act} />}
    </td>
  );
})()}

                      </tr>
                    );
                  })
              );
            })()}
          </tbody>
        </table>
      </div>
    )}
  </div>
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
