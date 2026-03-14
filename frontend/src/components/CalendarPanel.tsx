// components/CalendarPanel.tsx
import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon } from 'lucide-react';
import { Mukkadam, Allocation, Job } from '../types/types';
import LeaveModal from './leave';
import './calender.css';
import DayDetailModal from './DayDetail';
import { API_BASE_URL } from '../types/config';
import { toast } from './ui/sonner';
type PotentialStatus = 'PARTIAL' | 'NONE';
type MaxWorkRow = {
  mukkadamId: number;
  mukkadamName: string;
  activityId: number;
  activityName: string;
  productivity: number;
  availableWorkers: number;
  maxArea: number;
};

interface PotentialJob {
  date: string; 
  cropName:string,
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
  potentialRevenue: number;
  plotId: number;
  plotName: string;
  jobId: string;
}

// type PotentialByDate = Record<string, PotentialJob[]>;
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
interface CalendarPanelProps {
  currentMonth: Date;
  selectedDate: Date;
  allocations: Allocation[];
  potentialByDate?: Record<string, PotentialJob[]>;
  mukkadams: Mukkadam[];
  leaves: any[];
  allJobs?: Job[];
  onMonthChange: (date: Date) => void;
  onDateSelect: (date: Date) => void;
  onAllocationClick: (allocation: Allocation) => void;
  onLeavesUpdated: () => void;
  filters: CalendarFilters;
  refreshKey?: number;
  setFilters: React.Dispatch<React.SetStateAction<CalendarFilters>>;
  viewModes: ('jobs' | 'allocations' | 'potential'| 'payments' | 'insights')[];
  jobsByDate?: Record<string, Job[]>;
  jobs: Job[]; // pass all jobs for the month to show in day detail
  clusterId: number;
  overloadMap?: Record<string, any>;
  onStartAllocation: (jobId: string, activityId: number, activity: any) => void; // optional prop for overload data keyed by date
}


const CalendarPanel: React.FC<CalendarPanelProps> = ({
  currentMonth,
  selectedDate,
  allocations,
  mukkadams,
  allJobs,
filters,refreshKey,
setFilters,
  leaves,
  jobs,
  onMonthChange,
  onDateSelect,
  onAllocationClick,
  onStartAllocation,
  onLeavesUpdated,
  viewModes,
  jobsByDate,
  clusterId,
  potentialByDate,
  overloadMap = {},
}) => {

  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [leaveModalDate, setLeaveModalDate] = useState<Date>(new Date());

  const getDaysInMonth = () => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();

    const days: (Date | null)[] = [];

    // Empty cells before first day
    for (let i = 0; i < startingDayOfWeek; i++) {
      days.push(null);
    }

    // Actual days
    for (let day = 1; day <= daysInMonth; day++) {
      days.push(new Date(year, month, day));
    }

    return days;
  };
     const handleAllocationDateChange = async (allocation: Allocation) => {
  const newDateStr = window.prompt(
    'Move this allocation to date (YYYY-MM-DD):',
    allocation.allocated_date,
  );
  if (!newDateStr || newDateStr === allocation.allocated_date) return;

  // Check if target date is a general holiday
  try {
    const leaveResponse = await fetch(
      `${API_BASE_URL}/api/leaves/?start_date=${newDateStr}&end_date=${newDateStr}&cluster_id=${clusterId}`
    );
    const leaves = await leaveResponse.json();
    
    const generalHoliday = leaves.find((l: any) => 
      l.date === newDateStr && 
      l.leave_type === 'general' && 
      l.is_active
    );
    
    if (generalHoliday) {
      alert(`Cannot move allocation to this date: ${generalHoliday.reason || 'General Holiday'}`);
      return;
    }
  } catch (error) {
    console.error('Failed to check holiday status:', error);
    alert('Failed to verify target date. Please try again.');
    return;
  }

  // Proceed with allocation move
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/allocations/${allocation.id}/change_date/?cluster_id=${clusterId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allocated_date: newDateStr }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      let errorMessage = data.error || 'Failed to move allocation';
      
      if (data.warnings?.productivity_warning) {
        errorMessage += `\n\nProductivity Issue: ${data.warnings.productivity_warning.message}`;
      }
      
      alert(errorMessage);
      return;
    }

    alert('Allocation moved successfully');
    onLeavesUpdated();


    
  } catch (e) {
    console.error(e);
    alert('Network error: Failed to change allocation date');
  }
};
const handleAllocationDelete = async (allocation: Allocation) => {
  if (!window.confirm('Delete this allocation?')) return;

  try {
    const res = await fetch(
      `${API_BASE_URL}/api/allocations/${allocation.id}/delete_allocation/?cluster_id=${clusterId}`,
      { method: 'DELETE' },
    );

    if (res.ok) {
      onLeavesUpdated();

    } else {
      alert('Failed to delete allocation');
    }
  } catch (e) {
    console.error(e);
    alert('Failed to delete allocation');
  }
};
// CalendarPanel.tsx - getDayAllocations function

const getDayAllocations = (date: Date | null) => {
  if (!date) return [];
  const dateStr = formatDate(date);
  
  const dayAllocations = allocations.filter((a) => 
    formatDate(new Date(a.allocated_date)) === dateStr
  );

  // ✅ Use allJobs instead of jobs for lookup
  return dayAllocations.filter(alloc => {
    if (!filters?.activityId) return true;

    // ✅ Use allJobs (unfiltered) for lookup
    const job = (allJobs || jobs).find(j => j.job_id === alloc.job_id);
    if (!job) return true;

    const activity = job.activities?.find(a => a.id === alloc.job_activity);
    if (!activity) return true;

    return activity.activity_id === filters.activityId;
  });
};
const getDayLeaves = (date: Date | null) => {
  if (!date) return [];
  const dateStr = formatDate(date);
  return leaves?.filter((l) => l.date === dateStr && l.is_active) || [];
};

const getDayOverloads = (date: Date | null) => {
  if (!date) return [];
  const dateStr = formatDate(date);
  // overloadMap is currently keyed by `${job_id}-${activity_id}-${scheduled_date}`
  return Object.values(overloadMap).filter((o: any) => o.scheduled_date === dateStr);
};


const [showDayDetail, setShowDayDetail] = useState(false);
const [detailDate, setDetailDate] = useState<Date | null>(null);
const [detailCapacity, setDetailCapacity] = useState<any | null>(null);
const [dayTotals, setDayTotals] = useState<Record<string, number>>({});
// Add this helper
const getDayHasCarryForward = (date: Date | null) => {
  if (!date) return false;
  const dateStr = formatDate(date);
  return allocations.some(a => 
    formatDate(new Date(a.allocated_date)) === dateStr && 
    (a as any).is_carry_forward === true
  );
};


// Real daily availability from API: /mukkadams/daily_capacity_all/
const [availableMukkadamIds, setAvailableMukkadamIds] = useState<Set<number>>(new Set());
// ✅ CORRECT - explicit type annotation separate from initial value
const [availableByDate, setAvailableByDate] = useState<Record<string, Set<number>>>({});

const [crewSizeByDate, setCrewSizeByDate] = useState<Record<string, Record<number, number>>>({});


const fetchAvailableMukkadamsForDate = async (date: Date) => {
  const key = formatDate(date);
  try {
    const res = await fetch(
      `${API_BASE_URL}/api/mukkadams/daily_capacity_all/?date=${key}&cluster_id=${clusterId}`,
    );
    const data = await res.json() as { mukkadam_id: number; available_crew_size: number }[];

    // IDs of mukkadams that have at least 1 worker available today
    const ids = new Set<number>(
      data.filter(d => d.available_crew_size > 0).map(d => d.mukkadam_id)
    );

    // Per-mukkadam crew size for this specific date
    const crewSizes: Record<number, number> = {};
    data.forEach(d => { crewSizes[d.mukkadam_id] = d.available_crew_size; });

    setAvailableByDate(prev => ({ ...prev, [key]: ids }));
    setCrewSizeByDate(prev => ({ ...prev, [key]: crewSizes }));
  } catch (e) {
    console.error('Failed to fetch daily capacity_all', e);
  }
};


// 3. Fix reset effect — clear the map, not a Set
// CalendarPanel.tsx
// CalendarPanel.tsx — split into TWO separate effects

// Effect 1: Month change — full wipe and re-fetch everything

// Effect 1: Month change — wipe everything and re-fetch all days
useEffect(() => {
  setDayTotals({});
  setAvailableByDate({});
  setCrewSizeByDate({});
  days.forEach((d) => {
    if (d) {
      fetchAvailableMukkadamsForDate(d);
      fetchDayTotal(d);
    }
  });
}, [currentMonth]);
 // ← ONLY currentMonth, no refreshKey

useEffect(() => {
  if (!refreshKey) return;
  days.forEach((d) => {
    if (d) fetchDayTotal(d);
  });
}, [refreshKey]);

// Effect 3: Cluster change — wipe everything
useEffect(() => {
  setDayTotals({});
  setAvailableByDate({});
  setCrewSizeByDate({});
}, [clusterId]);


//              ↑ ADD THESE — triggers re-fetch after create/delete
const usedWorkersByMukkadam = new Map<number, number>();
allocations.forEach(a => {
  if ((a as any).allows_second_job === true) return;  // ← half-day, still free
  const current = usedWorkersByMukkadam.get(a.mukkadam) || 0;
  usedWorkersByMukkadam.set(a.mukkadam, current + (a.allocated_workers || 0));
});

const maxWorkMap = new Map<string, MaxWorkRow>();

mukkadams.forEach(m => {
  // AVAILABILITY GATE trust the API
  if (!availableMukkadamIds.has(m.mukkadam_id)) return; // not available today

  const baseCrew = (m as any).available_crew_size ?? m.crew_size ?? 0;

  const used = usedWorkersByMukkadam.get(m.mukkadam_id) || 0;
  const remainingWorkers = Math.max(baseCrew - used, 0);

  m.activity_rates.forEach((rate: any) => {
    const productivity = Number(rate.productivity_per_worker || 0);
    if (!productivity) return;

    const maxArea = remainingWorkers * productivity;
    if (maxArea <= 0) return;

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
const calculateDayCapacity = (date: Date | null) => {
  const EMPTY_RESULT = {
    status: 'good' as const,
    used: 0, total: 0, percentage: 0,
    conflicts: [], mukkadamsOnLeave: 0,
    neededAcres: 0, availableAcres: 0,
  };

  if (!date) return EMPTY_RESULT;

  const dateStr = formatDate(date);
  const isoDate = dateStr;

  const apiLoaded            = availableByDate[dateStr] !== undefined;
  const availableMukkadamIds = availableByDate[dateStr] ?? new Set<number>();
  const dailyCrewSizes       = crewSizeByDate[dateStr]  ?? {};

  const dayAllocations = getDayAllocations(date);
  const dayLeaves      = getDayLeaves(date);

  // 1. Holiday
  const generalHoliday = dayLeaves.find(l => l.leave_type === 'general');
  if (generalHoliday) {
    return {
      status: 'holiday' as const,
      used: 0, total: 0, percentage: 0, conflicts: [],
      reason: generalHoliday.reason || 'General Holiday',
      mukkadamsOnLeave: 0, neededAcres: 0, availableAcres: 0,
    };
  }

  // 2. Leaves
  const leaveByMukkadam = new Map<number, number>();
  dayLeaves.filter(l => l.leave_type === 'mukkadam').forEach(l => {
    leaveByMukkadam.set(l.mukkadam, (leaveByMukkadam.get(l.mukkadam) || 0) + (l.crew_on_leave || 0));
  });
  const mukkadamsOnLeaveIds = Array.from(leaveByMukkadam.keys());

  // 3. Used workers (excl half-day) — THIS DATE ONLY
  const usedWorkersByMukkadam = new Map<number, number>();
  allocations.forEach(a => {
    if (a.allocated_date?.slice(0, 10) !== isoDate) return; // ← THE FIX: only today
    if ((a as any).allows_second_job === true) return;
    usedWorkersByMukkadam.set(a.mukkadam, (usedWorkersByMukkadam.get(a.mukkadam) || 0) + (a.allocated_workers || 0));
  });

  // 4. Progress bar
  const totalCapacity = dayTotals[dateStr] ?? 0;
  const usedWorkers   = dayAllocations.reduce((sum, a) => sum + a.allocated_workers, 0);

  // 5. neededAcToday
  const jobsSource = allJobs || jobs;
  let neededAcToday = 0;
  const neededRows: any[] = [];

  jobsSource.forEach(job => {
    (job.activities || []).forEach((act: any) => {
      if (act.scheduled_date?.slice(0, 10) !== isoDate) return;
      const total = Number(act.total_area || 0);
      const allocatedHere = allocations
        .filter(a => a.job_id === job.job_id && a.job_activity === act.id)
        .reduce((x, a) => x + Number((a as any).allocated_area || 0), 0);
      const rem = Math.max(total - allocatedHere, 0);
      neededAcToday += rem;
      neededRows.push({ job: job.job_id, act: act.activity_name, total, allocatedHere, rem });
    });
  });

  // 6. canDoAcToday
  let canDoAcToday = 0;
  const canDoRows: any[] = [];

  if (apiLoaded) {
    mukkadams.forEach((m: any) => {
      const inAvailSet = availableMukkadamIds.has(m.mukkadam_id);
      const baseCrew   = dailyCrewSizes[m.mukkadam_id] ?? m.crew_size ?? 0;
      const used       = usedWorkersByMukkadam.get(m.mukkadam_id) || 0;
      const remaining  = Math.max(baseCrew - used, 0);
      const bestProd   = (m.activity_rates || []).reduce((b: number, r: any) => Math.max(b, Number(r.productivity_per_worker || 0)), 0);
      const hasHalfDay = allocations.some((a: any) =>
        a.mukkadam === m.mukkadam_id &&
        a.allocated_date?.slice(0, 10) === isoDate &&
        a.allows_second_job === true
      );
      const contrib = inAvailSet && remaining > 0 && bestProd > 0
        ? remaining * bestProd * (hasHalfDay ? 0.6 : 1)
        : 0;
      canDoAcToday += contrib;
      canDoRows.push({ name: m.mukkadam_name, id: m.mukkadam_id, inAvailSet, baseCrew, used, remaining, bestProd, hasHalfDay, contrib: +contrib.toFixed(2) });
    });
  }

  // 7. Conflicts
  const availableWorkersByMukkadam = new Map<number, number>();
  const maxWorkMap = new Map<string, MaxWorkRow>();

  if (apiLoaded) {
    mukkadams.forEach((m: any) => {
      if (!availableMukkadamIds.has(m.mukkadam_id)) return;
      const rawAvail = dailyCrewSizes[m.mukkadam_id] ?? m.crew_size ?? 0;
      const avail = Math.max(rawAvail - (leaveByMukkadam.get(m.mukkadam_id) || 0), 0);
      if (avail > 0) availableWorkersByMukkadam.set(m.mukkadam_id, avail);
      const rem = Math.max(rawAvail - (usedWorkersByMukkadam.get(m.mukkadam_id) || 0), 0);
      (m.activity_rates || []).forEach((rate: any) => {
        const prod = Number(rate.productivity_per_worker || 0);
        if (!prod || rem <= 0) return;
        const key = `${m.mukkadam_id}-${rate.activity_id}`;
        if (!maxWorkMap.has(key)) {
          maxWorkMap.set(key, { mukkadamId: m.mukkadam_id, mukkadamName: m.mukkadam_name, activityId: rate.activity_id, activityName: rate.activity_name, productivity: prod, availableWorkers: rem, maxArea: rem * prod });
        }
      });
    });
  }

  const maxWorkRows = Array.from(maxWorkMap.values());
  const neededWorkersByMukkadam = new Map<number, number>();
  jobsSource.forEach(job => {
    (job.activities || []).forEach((act: any) => {
      if (act.scheduled_date?.slice(0, 10) !== isoDate) return;
      if ((act as any).is_manually_moved) return;
      const remArea = Number(act.remaining_area ?? act.total_area ?? 0);
      if (remArea <= 0) return;
      maxWorkRows.filter(r => r.activityName === act.activity_name).forEach(r => {
        const needed = r.productivity > 0 ? Math.ceil(remArea / r.productivity) : 0;
        neededWorkersByMukkadam.set(r.mukkadamId, (neededWorkersByMukkadam.get(r.mukkadamId) || 0) + needed);
      });
    });
  });

  const conflicts: any[] = [];
  neededWorkersByMukkadam.forEach((needed, mukkadamId) => {
    const available = availableWorkersByMukkadam.get(mukkadamId) || 0;
    if (needed > available) {
      const m = mukkadams.find((mk: any) => mk.mukkadam_id === mukkadamId);
      conflicts.push({ type: 'worker_overload', mukkadamId, mukkadamName: m?.mukkadam_name || String(mukkadamId), neededWorkers: needed, availableWorkers: available, message: `${needed} needed but ${available} available` });
    }
  });

  // 8. Status
  let status: 'good' | 'warning' | 'error';
  let debugReason = '';
  const pct = neededAcToday > 0 && canDoAcToday > 0 ? (neededAcToday / canDoAcToday) * 100 : 0;

  if (!apiLoaded) {
    status = 'good'; debugReason = 'API_NOT_LOADED';
  } else if (neededAcToday === 0) {
    status = 'good'; debugReason = 'NO_JOBS';
  } else if (canDoAcToday === 0) {
    status = 'error'; debugReason = 'CANDO_IS_ZERO';
  } else if (pct <= 60) {
    status = 'good'; debugReason = `PCT_${pct.toFixed(1)}_UNDER_60`;
  } else if (pct <= 80) {
    status = 'warning'; debugReason = `PCT_${pct.toFixed(1)}_60_TO_80`;
  } else {
    status = 'error'; debugReason = `PCT_${pct.toFixed(1)}_OVER_80`;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // DEBUG: logs every RED or AMBER cell with full breakdown
  // Open DevTools Console → filter by "[CAL-DEBUG]"
  // ═══════════════════════════════════════════════════════════════════════════
  if (status !== 'good') {
    console.group(`[CAL-DEBUG] ${status === 'error' ? '🔴' : '🟡'} ${dateStr} → ${debugReason}`);
    console.log('apiLoaded:', apiLoaded);
    console.log('neededAcToday:', neededAcToday.toFixed(3), '| canDoAcToday:', canDoAcToday.toFixed(3), '| pct:', pct.toFixed(1) + '%');
    console.log('availableMukkadamIds size:', availableMukkadamIds.size, '→', [...availableMukkadamIds]);
    console.log('dailyCrewSizes:', dailyCrewSizes);
    console.log('mukkadams total loaded:', mukkadams.length);
    console.table(canDoRows);
    console.log('neededRows (jobs on this date):', neededRows);
    console.groupEnd();
  }

  return {
    status,
    used: usedWorkers,
    total: totalCapacity,
    percentage: totalCapacity > 0 ? (usedWorkers / totalCapacity) * 100 : 0,
    conflicts,
    mukkadamsOnLeave: mukkadamsOnLeaveIds.length,
    neededAcres: neededAcToday,
    availableAcres: canDoAcToday,
  };
};
const fetchDayTotal = async (date: Date) => {
  const key = formatDate(date);


  try {
    const res = await fetch(
      `${API_BASE_URL}/api/mukkadams/day_total_capacity/?date=${key}&cluster_id=${clusterId}`,
    );
    const data = await res.json();
    setDayTotals(prev => ({ ...prev, [key]: data.total_capacity }));
  } catch (e) {
    console.error('Failed day total', e);
  }
};

const formatDate = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};


  const handlePrevMonth = () => {
    const newDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1);
    onMonthChange(newDate);
  };

  const handleNextMonth = () => {
    const newDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1);
    onMonthChange(newDate);
  };

  const isSelectedDate = (date: Date | null) => {
    if (!date) return false;
    return formatDate(date) === formatDate(selectedDate);
  };
const handleDateClick = (date: Date | null) => {
  if (!date) return;

  onDateSelect(date);

  const capacity = calculateDayCapacity(date);
  setDetailDate(date);
  setDetailCapacity(capacity);
  setShowDayDetail(true);
};


  const handleDateRightClick = (e: React.MouseEvent, date: Date | null) => {
    e.preventDefault();
    if (!date) return;
    setLeaveModalDate(date);
    setShowLeaveModal(true);
  };

  const days = getDaysInMonth();

useEffect(() => {
  setDayTotals({});
  setAvailableMukkadamIds(new Set());
}, [clusterId]);

  return (
    <div className="calendar-panel">
      <div className="panel-header">
        <div className="calendar-header">
          <button className="nav-button" onClick={handlePrevMonth}>
            <ChevronLeft size={20} />
          </button>
          <h2 className="calendar-month">
            {currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
          </h2>
          <button className="nav-button" onClick={handleNextMonth}>
            <ChevronRight size={20} />
          </button>
        </div>
      </div>

      <div className="calendar-grid">
        {/* Day names */}
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
          <div key={day} className="day-name">
            {day}
          </div>
        ))}

        {/* Calendar days */}
{days.map((date, index) => {
  if (!date) {
    return <div key={`empty-${index}`} className="day-cell empty" />;
  }

  const dayAllocs = getDayAllocations(date);
  const capacity = calculateDayCapacity(date);
  const isSelected = isSelectedDate(date);
  const dayOverloads = getDayOverloads(date);
  const hasOverload = dayOverloads.some((o: any) => o.overloaded);

  const dateKey = formatDate(date);
  const dayJobs = jobsByDate?.[dateKey] || [];

const dayPotential = potentialByDate?.[dateKey] || [];
const hasPotential = dayPotential.length > 0;
const hasCarryForward = getDayHasCarryForward(date);

return (
  <div
    key={dateKey}
    className={`day-cell ${capacity.status} ${isSelected ? 'selected' : ''} ${hasOverload ? 'overload' : ''} ${hasCarryForward ? 'carry-forward-day' : ''}`}
    
      onClick={() => handleDateClick(date)}
      onContextMenu={(e) => handleDateRightClick(e, date)}
    >
      {/* Header row */}
      <div className="day-header-row">
        <span className="day-number">{date.getDate()}</span>

        <div className="day-status-group">
          {/* Capacity ratio */}
          {capacity.status !== 'holiday'  && (
            <span className="mini-capacity">
              {capacity.total}w
              {/* {capacity.used}/{capacity.total}w */}
            </span>
          )}

          {/* Mukkadams on leave */}
          {capacity.mukkadamsOnLeave > 0 && (
            <span
              className="leave-indicator"
              title={`${capacity.mukkadamsOnLeave} mukkadams on leave`}
            >
              🔵{capacity.mukkadamsOnLeave}
            </span>
          )}

          {/* Conflicts */}
          {/* {capacity.conflicts.length > 0 && (
            <span
              className="mini-conflict"
              title={`${capacity.conflicts.length} conflicts`}
            >
              ⚠️{capacity.conflicts.length}
            </span>
          )} */}
        </div>
      </div>

      {/* Holiday badge */}
      {capacity.status === 'holiday' && (
        <div className="capacity-badge holiday">🏖️ Holiday</div>
      )}

      {/* Jobs count – only in Jobs view */}
{/* Jobs count – only in Jobs view, exclude manually moved activities */}
{viewModes.includes('jobs') && dayJobs.length > 0 && (() => {
  let aiActive = 0;   // scheduled normally, not moved away, not moved in
  let aiMoved  = 0;   // originally AI but moved away to another date

  dayJobs.forEach(job => {
    (job.activities || []).forEach((act: any) => {
      if ((act as any).is_manually_moved) return; // H job, skip

      const movedAway =
        !(act as any).is_manually_moved &&
        (act as any).moved_to_date != null;

      if (movedAway) {
        aiMoved++;
      } else {
        aiActive++;
      }
    });
  });

  const total = aiActive + aiMoved;
  if (total === 0) return null;

  return (
    <div className="capacity-badge jobs-badge flex items-center gap-1">
      <span>{aiActive} ai</span>
      {aiMoved > 0 && (
        <span
          className="text-[9px] font-bold text-amber-600 bg-amber-50 border border-amber-200 rounded-full px-1"
          title={`${aiMoved} AI job${aiMoved > 1 ? 's' : ''} moved to another date`}
        >
          {aiActive}/{total}
        </span>
      )}
    </div>
  );
})()}

      {(viewModes.includes('potential')) && hasPotential && (
        <div className="capacity-badge potential-badge">
          {dayPotential.length} potential
        </div>
      )}

      {/* Allocations count – only in Allocations view */}
{viewModes.includes('allocations') && (() => {
  const hCount = jobs.reduce((sum, job) =>
    sum + (job.activities || []).filter(act =>
      act.scheduled_date?.slice(0, 10) === dateKey &&
      (act as any).is_manually_moved === true
    ).length, 0
  );

  // ✅ Count carry-forward allocations for this day
  const carryForwardCount = dayAllocs.filter(a => (a as any).is_carry_forward).length;
  const normalAllocCount = dayAllocs.filter(a => !(a as any).is_carry_forward).length;

  return (
    <div className="allocation-chips">
      {hCount > 0 && (
        <div className="allocation-chip" style={{ backgroundColor: '#fff7ed', color: '#c2410c', fontWeight: 700 }}>
          {hCount} H
        </div>
      )}
      {normalAllocCount > 0 && (
        <div className="allocation-chip" style={{ backgroundColor: '#dbeafe', color: '#1d4ed8', fontWeight: 700 }}>
          {normalAllocCount} alloc
        </div>
      )}
      {/* ✅ Carry-forward badge */}
      {carryForwardCount > 0 && (
        <div className="allocation-chip" style={{ backgroundColor: '#f3e8ff', color: '#7c3aed', fontWeight: 700 }}>
          🔄 {carryForwardCount} CF
        </div>
      )}
    </div>
  );
})()}
      {/* Allocations count */}
      
    </div>
  );
})}

      </div>

      {/* Leave Modal */}
      {showLeaveModal && (
        <LeaveModal
          selectedDate={leaveModalDate}
          mukkadams={mukkadams}
          existingLeaves={leaves.filter((l) => l.date === formatDate(leaveModalDate))}
          onClose={() => setShowLeaveModal(false)}
          onLeaveMarked={onLeavesUpdated}
          clusterId={clusterId} 
        />
      )}
{showDayDetail && detailDate && detailCapacity && (
  <DayDetailModal
    date={detailDate}
jobs={jobs.filter(job => {
  const dateStr = formatDate(detailDate);
  
  // ✅ Has activity scheduled on this date
  const hasScheduledActivity = (job.activities || []).some(
    a => a.scheduled_date?.slice(0, 10) === dateStr
  );
  
  // ✅ Has allocation on this date
  const hasAllocationOnDate = getDayAllocations(detailDate).some(
    a => a.job_id === job.job_id
  );
  
  return hasScheduledActivity || hasAllocationOnDate;
}).map(job => ({
  ...job,
  activities: (job.activities || []).filter(a => {
    const dateStr = formatDate(detailDate);
    const scheduledMatch = a.scheduled_date?.slice(0, 10) === dateStr;
    
    // ✅ Also include activities that have allocations on this date
    const hasAlloc = getDayAllocations(detailDate).some(
      alloc => alloc.job_id === job.job_id && alloc.job_activity === a.id
    );
    
    return scheduledMatch || hasAlloc;
  })
}))}
    allocations={getDayAllocations(detailDate)}
    onLeavesUpdated={onLeavesUpdated}   
    mukkadams={mukkadams}
    capacitySummary={detailCapacity}
    leaves={getDayLeaves(detailDate)}
    overloads={getDayOverloads(detailDate)}  
    onClose={() => setShowDayDetail(false)}
    onAllocationDateChange={(job, allocation) => handleAllocationDateChange(allocation)}
onAllocationDelete={handleAllocationDelete}
    onStartAllocation={onStartAllocation}
    potentialJobs={potentialByDate?.[formatDate(detailDate)] || []}
    filters={filters}
    allJobs={allJobs || jobs}
    viewMode={viewModes}  // pass the array directly, not viewModes[clusterId]
    clusterId={clusterId}
  />
)}
    </div>
  );
};

export default CalendarPanel;
