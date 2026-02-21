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

const maxWorkRows: MaxWorkRow[] = [];

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
    // onLeavesUpdated(); // Refresh allocations
  } catch (error) {
    toast.error('Failed to update allocation');
    console.error(error);
  }
};

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
      } else {
        toast.success(`Fully allocated ${areaToAllocate} ac to ${mukkadam.mukkadam_name}`);
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
  const baseCrew = (m as any).available_crew_size ?? m.crew_size ?? 0;
  const used = usedWorkersByMukkadam.get(m.mukkadam_id) || 0;
  const remainingWorkers = Math.max(baseCrew - used, 0);

  // ✅ REMOVED: if (remainingWorkers <= 0) return;  ← this was hiding 0-worker mukkadams

  (m.activity_rates || []).forEach((rate: any) => {
    const productivity = Number(rate.productivity_per_worker || 0);
    if (!productivity) return;

    const maxArea = remainingWorkers * productivity;  // ✅ will be 0 on holiday
    const key = `${m.mukkadam_id}-${rate.activity_id}`;

    if (!maxWorkMap.has(key)) {
      maxWorkMap.set(key, {
        mukkadamId: m.mukkadam_id,
        mukkadamName: m.mukkadam_name,
        activityId: rate.activity_id,
        activityName: rate.activity_name,
        productivity,
        availableWorkers: remainingWorkers,  // ✅ shows 0
        maxArea,                             // ✅ shows 0
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
    Jobs ({jobsOnThisDay.length})
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
{/* TAB 1: ALLOCATIONS */}
{activeTab === 'allocations' && (
  <div className="tab-content">
    {/* Leaves Section - Improved Styling */}
    {leaves.length > 0 && (
      <div className="mb-4 space-y-2">
        <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Attendance Alerts</div>
        {leaves.map(l => (
          <div key={l.id} className={`leave-alert-row p-2 rounded border-l-4 ${l.leave_type === 'general' ? 'bg-blue-50 border-blue-400 text-blue-700' : 'bg-red-50 border-red-400 text-red-700'}`}>
            {l.leave_type === 'general' ? (
              <span className="text-sm font-medium">🏖️ Holiday: {l.reason}</span>
            ) : (
              <span className="text-sm font-medium">👤 {l.mukkadam_name}: {l.crew_on_leave} workers absent</span>
            )}
          </div>
        ))}
      </div>
    )}

    {/* Section Header */}
    <div className="form-divider mb-4">Active Allocations ({filteredAllocations.length})</div>

    {filteredAllocations.length === 0 ? (
      <p className="empty-text">No allocations made for this day.</p>
    ) : (
      <div className="space-y-4">
        {filteredAllocations.map(a => {
          const m = mukkadams.find(mk => mk.mukkadam_id === a.mukkadam);
          const job = (allJobs || jobs).find(j => j.job_id === a.job_id);

          return (
            <div key={a.id} className="allocation-row card-style border-l-4 border-green-500 hover:shadow-md transition-shadow">
              <div className="allocation-main">
                <div className="flex justify-between items-start">
                  <div className="item-title flex items-center gap-2 text-lg font-bold text-gray-800">
                    <Tractor size={18} className="text-green-600" /> 
                    {a.activity_name}
                  </div>
                  {/* Status Badge */}
                  <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-[10px] font-bold uppercase">
                    Allocated
                  </span>
                </div>
                
                {/* Information Grid */}
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div className="flex flex-col">
                    <span className="text-[10px] text-gray-400 uppercase font-bold">Farmer & Plot</span>
                    <div className="text-sm text-gray-700 truncate">
                      <strong>{job?.farmer_name}</strong> · {job?.plot_name}
                    </div>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[10px] text-gray-400 uppercase font-bold">Crop Details</span>
                    <div className="text-sm text-gray-600 italic">
                      {job?.crop_name} ({job?.variety})
                    </div>
                  </div>
                </div>

                {/* Metrics Bar */}
                <div className="flex items-center gap-4 mt-3 pt-3 border-t border-gray-100">
                  <div className="flex items-center gap-1 text-sm font-semibold text-gray-700">
                    <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                    {a.allocated_area} ac
                  </div>
                  <div className="flex items-center gap-1 text-sm font-semibold text-gray-700">
                    <Users size={14} className="text-gray-400" />
                    {a.allocated_workers} Workers
                  </div>
                  <div className="ml-auto text-xs text-gray-500 bg-gray-50 px-2 py-1 rounded border border-gray-200">
                    Team: <span className="font-bold text-gray-700">{m?.mukkadam_name || 'N/A'}</span>
                  </div>
                </div>
              </div>

              {/* <div className="allocation-actions mt-3 flex justify-end gap-2 border-t pt-2">
                <button
                  className="px-3 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded transition"
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
                </button>
                <button 
                  className="px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded transition" 
                  onClick={() => onAllocationDelete(a)}
                >
                  Remove
                </button>
              </div> */}
            </div>
          );
        })}

        {/* {jobsOnThisDay.length > 0 && (
  <div className="quick-allocate-section" style={{ marginBottom: '1rem' }}>
    <div className="form-divider">Jobs Scheduled Today</div>
    {jobsOnThisDay.map(job =>
      job.activities
        .filter(act => act.scheduled_date?.slice(0, 10) === isoDate)
        .map(act => {
          const isAllocated = Number(act.allocated_area) > 0;
          const isFullyAllocated = Number(act.allocated_area) >= Number(act.total_area);

          // Find allocation record for this activity (from filteredAllocations)
          const existingAllocation = allocations.find(
            a => a.job_id === job.job_id && a.job_activity === act.id
          );

          const mukkadam = mukkadams.find(m =>
            m.activity_rates?.some((r: any) =>
              r.activity_id === act.activity_id ||
              r.activity_name === act.activity_name
            )
          );
          const rate = mukkadam?.activity_rates?.find((r: any) =>
            r.activity_id === act.activity_id ||
            r.activity_name === act.activity_name
          );
          const productivity = Number(rate?.productivity_per_worker || 0);

          // ✅ Remaining workers = crew - already allocated workers today
          const usedWorkers = usedWorkersByMukkadam.get(mukkadam?.mukkadam_id || 0) || 0;
          const availableWorkers = Math.max((mukkadam?.crew_size || 0) - usedWorkers, 0);
          const area = parseFloat((availableWorkers * productivity).toFixed(2));

          // Allocated mukkadam details
          const allocatedMukkadam = existingAllocation
            ? mukkadams.find(m => m.mukkadam_id === existingAllocation.mukkadam)
            : null;

          return (
            <div
              key={`${job.job_id}-${act.id}`}
              className="allocation-row card-style"
              style={{
                borderLeft: isFullyAllocated
                  ? '3px solid #10b981'
                  : isAllocated
                  ? '3px solid #f59e0b'
                  : '3px solid #e5e7eb',
              }}
            >
              <div style={{ flex: 1 }}>
                <div className="item-title">{act.activity_name}</div>
                <div style={{ fontSize: '0.85rem', color: '#475569' }}>
                  <strong>{job.farmer_name}</strong> · {job.plot_name} · {job.crop_name}
                </div>

                {isAllocated ? (
                  // ✅ Show allocation details
                  <div style={{ marginTop: '4px' }}>
                    <div className="item-meta" style={{ color: isFullyAllocated ? '#10b981' : '#f59e0b' }}>
                      {isFullyAllocated ? '✅' : '🔶'} {act.allocated_area}/{act.total_area} ac allocated
                      {!isFullyAllocated && ` · ${act.remaining_area} ac remaining`}
                    </div>
                    {existingAllocation && (
                      <div className="item-sub" style={{ color: '#475569', fontSize: '0.82rem' }}>
                        Team: <strong>{allocatedMukkadam?.mukkadam_name || 'N/A'}</strong>
                        {' · '}{existingAllocation.allocated_workers} workers
                        {' · '}{existingAllocation.allocated_area} ac
                        {existingAllocation.mukkadam_rate > 0 && (
                          <span> · ₹{existingAllocation.mukkadam_rate}/ac</span>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  
                  <div className="item-meta" style={{ color: '#6b7280', marginTop: '4px' }}>
                    Not allocated · {act.remaining_area} ac remaining
                    {mukkadam && availableWorkers > 0 && area > 0 && (
                      <span style={{ marginLeft: '0.5rem' }}>
                        → {mukkadam.mukkadam_name}: {availableWorkers}w × {productivity} = {area} ac
                      </span>
                    )}
                    {mukkadam && availableWorkers === 0 && (
                      <span style={{ color: '#dc2626', marginLeft: '0.5rem' }}>
                        · No workers available today
                      </span>
                    )}
                  </div>
                )}
              </div>

              <div className="allocation-actions">
                
                {!isAllocated && (
                  <button
                    className="btn-primary"
                    style={{ whiteSpace: 'nowrap' }}
                    disabled={!mukkadam || !area || availableWorkers === 0}
                    onClick={() => handleQuickAllocate(job, act)}
                    title={!mukkadam ? 'No mukkadam with rate card' : availableWorkers === 0 ? 'No workers available' : ''}
                  >
                    ⚡ Allocate
                  </button>
                )}

                
                {isAllocated && existingAllocation && (
                  <>
                    <button
                      className="btn-link"
                      onClick={() => onAllocationDateChange(job, existingAllocation)}
                    >
                      Move
                    </button>
                    <button
                      className="btn-link delete"
                      onClick={() => onAllocationDelete(existingAllocation)}
                    >
                      Remove
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })
    )}
  </div>
)} */}
      </div>
    )}
  </div>
)}

{/* Jobs scheduled today — Quick Allocate section */}


{/* Edit Allocation Modal */}
{showEditAllocationModal && editingAllocation && (
  <div className="modal-overlay" onClick={() => setShowEditAllocationModal(false)}>
    <div className="modal-content modal-md" onClick={(e) => e.stopPropagation()}>
      <div className="modal-header">
        <h3 className="modal-title">Edit Allocation</h3>
        <button onClick={() => setShowEditAllocationModal(false)} className="modal-close">
          <X size={20} />
        </button>
      </div>

      <div className="modal-body">
        {/* Activity (Read-only) */}
        <div className="form-group">
          <label className="form-label">Activity</label>
          <input
            type="text"
            value={editingAllocation.activity_name}
            className="form-input"
            disabled
            style={{ backgroundColor: '#f3f4f6', cursor: 'not-allowed' }}
          />
        </div>

        {/* Mukkadam */}
        <div className="form-group">
          <label className="form-label">Mukkadam *</label>
          <select
            className="form-select"
            value={editForm.mukkadam_id}
            onChange={(e) => {
              const id = parseInt(e.target.value);
              setEditForm({ ...editForm, mukkadam_id: id });
            }}
            required
          >
            <option value="">Select mukkadam</option>
            {mukkadams.map((m) => (
              <option key={m.mukkadam_id} value={m.mukkadam_id}>
                {m.mukkadam_name} (Crew: {m.crew_size})
              </option>
            ))}
          </select>
          {Number(editForm.mukkadam_rate) > 0 && (
  <small className="form-help" style={{ color: '#10b981' }}>
    Rate: ₹{Number(editForm.mukkadam_rate).toFixed(2)}/acre
  </small>
)}

        </div>

        {/* Date */}
        <div className="form-group">
          <label className="form-label">Date *</label>
          <input
            type="date"
            className="form-input"
            value={editForm.allocated_date}
            onChange={(e) => setEditForm({ ...editForm, allocated_date: e.target.value })}
            required
          />
        </div>

        {/* Workers */}
        <div className="form-group">
          <label className="form-label">Workers *</label>
          <input
            type="number"
            className="form-input"
            value={editForm.allocated_workers}
            onChange={(e) => {
              const workers = parseInt(e.target.value) || 0;
              setEditForm({ ...editForm, allocated_workers: workers });
            }}
            required
          />
          {availableWorkers !== null && (
            <small className="form-help">
              Available on {editForm.allocated_date}: {availableWorkers} workers
              {editForm.allocated_workers > availableWorkers && (
                <span style={{ color: '#dc2626', display: 'block' }}>
                  ⚠️ Exceeds available capacity
                </span>
              )}
            </small>
          )}
        </div>

        {/* Area */}
        <div className="form-group">
          <label className="form-label">Area (acres) *</label>
          <input
            type="number"
            step="0.01"
            className="form-input"
            value={editForm.allocated_area}
            onChange={(e) => {
              const area = parseFloat(e.target.value) || 0;
              setEditForm({ ...editForm, allocated_area: area });
            }}
            required
          />
          {maxCapacity !== null && (
            <small className="form-help">
              Max capacity with {editForm.allocated_workers} workers: {maxCapacity.toFixed(2)} acres
              {editForm.allocated_area > maxCapacity && (
                <span style={{ color: '#dc2626', display: 'block' }}>
                  ⚠️ Exceeds team capacity
                </span>
              )}
            </small>
          )}
        </div>

        {/* Summary */}
        <div className="allocation-summary" style={{
          padding: '1rem',
          backgroundColor: '#f0f9ff',
          borderRadius: '8px',
          marginTop: '1rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span>Farmer Rate:</span>
            <strong>₹{editingAllocation.farmer_rate}/acre</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span>Mukkadam Rate:</span>
            <strong>
  ₹{typeof editForm.mukkadam_rate === "number"
    ? editForm.mukkadam_rate.toFixed(2)
    : "0.00"}
  /acre
</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '0.5rem', borderTop: '1px solid #cbd5e1' }}>
            <span>Profit Margin:</span>
            <strong style={{ color: '#10b981' }}>
              ₹{((editingAllocation.farmer_rate - editForm.mukkadam_rate) * editForm.allocated_area).toFixed(2)}
            </strong>
          </div>
        </div>
      </div>

      <div className="modal-footer">
        <button
          onClick={() => {
            setShowEditAllocationModal(false);
            setEditingAllocation(null);
          }}
          className="btn-secondary"
        >
          Cancel
        </button>
        <button
          onClick={handleEditAllocation}
          className="btn-primary"
          disabled={
            !editForm.mukkadam_id ||
            !editForm.allocated_date ||
            editForm.allocated_workers <= 0 ||
            editForm.allocated_area <= 0 ||
            (maxCapacity !== null && editForm.allocated_area > maxCapacity) ||
            (availableWorkers !== null && editForm.allocated_workers > availableWorkers)
          }
        >
          Save Changes
        </button>
      </div>
    </div>
  </div>
)}


  {/* TAB 2: JOBS */}
{/* TAB 2: JOBS */}
{activeTab === 'jobs' && (
  <div className="tab-content">
    {jobsOnThisDay.length === 0 ? (
      <p className="text-sm text-gray-400 italic mt-4">No jobs scheduled.</p>
    ) : (
      <div className="mt-2 rounded-xl border border-gray-200 overflow-x-auto">
        <table className="text-sm" style={{ minWidth: '750px', width: '100%' }}>
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500">Farmer</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500">Plot / Crop</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500">Activity</th>
              <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500">Area (ac)</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500">Workers Required</th>
              {(() => {
  const modes = Array.isArray(viewMode) ? viewMode : [viewMode];
  return modes.includes('allocations') || modes.includes('both');
})() && (
  <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-500">Action</th>
)}
            </tr>
          </thead>
          <tbody>
            {(() => {
              // ── check if this day is in the past ──
              const today = new Date();
              today.setHours(0, 0, 0, 0);
              const isPastDay = date < today;

              return jobsOnThisDay.flatMap(job =>
                job.activities
                  .filter(act => {
  if (act.scheduled_date?.slice(0, 10) !== isoDate) return false;
  
  // ← temporarily remove this to test:
  // if (Number(act.remaining_area) <= 0) return false;
  
  const modes = Array.isArray(viewMode) ? viewMode : [viewMode];
  const isManual = (act as any).is_manually_moved === true;
  if (modes.includes('both' as any)) return true;
  if (modes.includes('jobs') && modes.includes('allocations')) return true;
  if (modes.includes('allocations') && !modes.includes('jobs')) return isManual;
  return !isManual;
})
                  .map(act => {
                    const workerRows = maxWorkRows.filter(r => r.activityName === act.activity_name);

                    return (
                      <tr key={`${job.job_id}-${act.id}`} className="border-b border-gray-100 hover:bg-gray-50 transition">
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
                            {job.crop_name || '—'}{job.variety ? ` • ${job.variety}` : ''}
                          </p>
                        </td>

                        {/* Activity */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="px-2 py-0.5 bg-teal-50 text-teal-700 rounded-full text-xs font-medium">
                              {act.activity_name}
                            </span>
                            {(act as any).is_manually_moved ? (
                              <span className="px-1.5 py-0.5 bg-orange-100 text-orange-600 rounded text-[10px] font-bold">H</span>
                            ) : (
                              <span className="px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded text-[10px] font-bold">AI</span>
                            )}
                          </div>
                        </td>

                        {/* Area */}
                        <td className="px-4 py-3 text-right">
                          <span className="font-semibold text-gray-800">{act.remaining_area}</span>
                          <span className="text-xs text-gray-400 ml-1">ac</span>
                        </td>

                        {/* Workers Required */}
                        <td className="px-4 py-3">
                          {workerRows.length === 0 ? (
                            <span className="text-xs text-gray-400 italic">No team data</span>
                          ) : (
                            <div className="flex flex-col gap-1">
                              {workerRows.map((r, i) => {
                                const needed = r.productivity > 0
                                  ? Math.ceil(Number(act.remaining_area) / r.productivity)
                                  : '—';

                                const canDo = !isPastDay &&
                                  typeof needed === 'number' &&
                                  needed <= r.availableWorkers &&
                                  r.availableWorkers > 0;

                                const handleTeamClick = () => {
                                  if (!canDo) return;

                                  const mukkadam = mukkadams.find(m => m.mukkadam_id === r.mukkadamId);
                                  if (!mukkadam) return;

                                  const rate = mukkadam.activity_rates?.find((rt: any) =>
                                    rt.activity_id === act.activity_id || rt.activity_name === act.activity_name
                                  );

                                  // ── confirmation toast / confirm ──
                                  const confirmed = window.confirm(
                                    `Allocate ${act.remaining_area} ac of "${act.activity_name}" to ${r.mukkadamName}?\n\n` +
                                    `Workers: ${needed}  |  Rate: ₹${rate?.rate_per_acre || 0}/ac`
                                  );
                                  if (!confirmed) return;

                                  const enrichedAct = {
                                    ...act,
                                    __prefill: {
                                      mukkadam_id: r.mukkadamId,
                                      allocated_workers: needed,
                                      allocated_area: Number(act.remaining_area),
                                      mukkadam_rate: Number(rate?.rate_per_acre || 0),
                                    }
                                  };
                                  onStartAllocation(job.job_id, act.id, enrichedAct);
                                };

                                return (
                                  <div key={i} className="flex items-center gap-2">
                                    <button
                                      type="button"
                                      disabled={!canDo}
                                      onClick={handleTeamClick}
                                      title={
                                        isPastDay
                                          ? 'Past date — cannot allocate'
                                          : r.availableWorkers === 0
                                          ? 'On holiday'
                                          : canDo
                                          ? `Click to allocate ${act.remaining_area} ac to ${r.mukkadamName}`
                                          : `Not enough workers (need ${needed}, have ${r.availableWorkers})`
                                      }
                                      className={`text-xs w-28 truncate text-left transition rounded px-1 py-0.5 ${
                                        isPastDay || r.availableWorkers === 0 || !canDo
                                          ? 'text-gray-400 cursor-not-allowed'
                                          : 'text-teal-700 font-semibold underline underline-offset-2 hover:bg-teal-50 cursor-pointer'
                                      }`}
                                    >
                                      {r.mukkadamName}
                                    </button>

                                    {r.availableWorkers === 0 ? (
                                      <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-gray-100 text-gray-400">
                                        🏖️ Holiday
                                      </span>
                                    ) : (
                                      <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                                        isPastDay
                                          ? 'bg-gray-100 text-gray-400'
                                          : canDo
                                          ? 'bg-green-50 text-green-700'
                                          : 'bg-red-50 text-red-600'
                                      }`}>
                                        {needed} needed
                                      </span>
                                    )}

                                    <span className="text-xs text-gray-400">/ {r.availableWorkers} avail</span>

                                    {canDo && (
                                      <span className="text-teal-500 text-xs">⚡</span>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </td>

                        {/* Action — only show Move if NOT past day */}
                        {(() => {
  const modes = Array.isArray(viewMode) ? viewMode : [viewMode];
  return modes.includes('allocations') || modes.includes('both');
})() && (
  <td className="px-4 py-3 text-center">
    {isPastDay ? <span className="text-xs text-gray-300 italic">Past</span> : <MoveJobButton job={job} act={act} />}
  </td>
)}
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
