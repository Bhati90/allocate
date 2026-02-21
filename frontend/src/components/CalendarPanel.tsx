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
  setFilters: React.Dispatch<React.SetStateAction<CalendarFilters>>;
  viewModes: ('jobs' | 'allocations' | 'potential'| 'payments')[];
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
filters,
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

const calculateDayCapacity = (date: Date | null) => {
  if (!date) return { status: 'empty', used: 0, total: 0, percentage: 0, conflicts: [], mukkadamsOnLeave: 0 };

  const dateStr = formatDate(date);
  const dayAllocations = getDayAllocations(date);
  const dayLeaves = getDayLeaves(date);

  // 1) General holiday
  const generalHoliday = dayLeaves.find((l) => l.leave_type === 'general');
  if (generalHoliday) {
    return {
      status: 'holiday',
      used: 0,
      total: 0,
      percentage: 0,
      conflicts: [],
      reason: generalHoliday.reason || 'General Holiday',
      mukkadamsOnLeave: 0,
    };
  }

  // 2) Sum leaves per mukkadam for this day
  const leaveByMukkadam = new Map<number, number>();
  dayLeaves
    .filter((l) => l.leave_type === 'mukkadam')
    .forEach((l) => {
      // adjust key name if your API returns mukkadam_id instead of mukkadam
      const id = l.mukkadam;
      const current = leaveByMukkadam.get(id) || 0;
      leaveByMukkadam.set(id, current + (l.crew_on_leave || 0));
    });

  const mukkadamsOnLeaveIds = Array.from(leaveByMukkadam.keys());

  // 3) Build per-mukkadam-per-activity capacity using EFFECTIVE crew
  const mukkadamActivityMap = new Map<
    string,
    {
      mukkadam: Mukkadam;
      activity: string;
      allocations: Allocation[];
      totalArea: number;
      maxCapacity: number;
      efficiency: number;
      effectiveCrew: number;
    }
  >();

  dayAllocations.forEach((alloc) => {
    const mukkadam = mukkadams.find((m) => m.mukkadam_id === alloc.mukkadam);
    if (!mukkadam) return;

    const leaveCount = leaveByMukkadam.get(mukkadam.mukkadam_id) || 0;
    const effectiveCrew = Math.max(mukkadam.crew_size - leaveCount, 0);

    const key = `${alloc.mukkadam}-${alloc.activity_name}`;

    if (!mukkadamActivityMap.has(key)) {
      // productivity for this activity
      const activityRate = mukkadam.activity_rates?.find(
        (r: any) => r.activity_name === alloc.activity_name
      );
      const efficiency = activityRate?.productivity_per_worker || 0.15;

      // max capacity for THIS allocation set: use effective crew, not allocated_workers
      const maxCapacity = effectiveCrew * efficiency;

      mukkadamActivityMap.set(key, {
        mukkadam,
        activity: alloc.activity_name,
        allocations: [alloc],
        totalArea: alloc.allocated_area,
        maxCapacity,
        efficiency,
        effectiveCrew,
      });
    } else {
      const entry = mukkadamActivityMap.get(key)!;
      entry.allocations.push(alloc);
      entry.totalArea += alloc.allocated_area;
    }
  });

  // 4) Conflicts and overloads
  const conflicts: any[] = [];
  let totalUsedPercentage = 0;

  mukkadamActivityMap.forEach((entry) => {
    const { mukkadam, activity, totalArea, maxCapacity, allocations } = entry;

    if (totalArea > maxCapacity) {
      conflicts.push({
        type: 'overload',
        mukkadam: mukkadam.mukkadam_name,
        activity,
        needed: totalArea,
        available: maxCapacity,
        deficit: totalArea - maxCapacity,
        allocations,
      });
    }

    const usagePercent = maxCapacity > 0 ? (totalArea / maxCapacity) * 100 : 0;
    totalUsedPercentage += usagePercent;
  });

  // 5) Same mukkadam doing multiple activities
  const mukkadamActivities = new Map<number, string[]>();
  dayAllocations.forEach((alloc) => {
    if (!mukkadamActivities.has(alloc.mukkadam)) {
      mukkadamActivities.set(alloc.mukkadam, []);
    }
    if (!mukkadamActivities.get(alloc.mukkadam)!.includes(alloc.activity_name)) {
      mukkadamActivities.get(alloc.mukkadam)!.push(alloc.activity_name);
    }
  });

  mukkadamActivities.forEach((activities, mukkadamId) => {
    if (activities.length > 1) {
      const mukkadam = mukkadams.find((m) => m.mukkadam_id === mukkadamId);
      conflicts.push({
        type: 'multiple_activities',
        mukkadam: mukkadam?.mukkadam_name || 'Unknown',
        activities,
        message: `Same team assigned to ${activities.length} activities`,
      });
    }
  });

  // 6) Status
  let status: 'good' | 'warning' | 'caution' | 'error' | 'empty' = 'good';
  if (conflicts.length > 0) {
    status = 'error';
  } else if (totalUsedPercentage >= 90) {
    status = 'warning';
  } else if (totalUsedPercentage >= 70) {
    status = 'caution';
  }

  // 7) Total capacity and used workers (both consider leaves)
// 7) Total capacity and used workers (both consider leaves)
// Use precomputed per-day total from backend, fallback to 0
const totalCapacity = dayTotals[dateStr] ?? 0;



  const usedWorkers = dayAllocations.reduce((sum, a) => sum + a.allocated_workers, 0);

  if (dayAllocations.length === 0 && totalCapacity === 0) {
    status = 'empty';
  }

  return {
    status,
    used: usedWorkers,
    total: totalCapacity,
    percentage: totalCapacity > 0 ? (usedWorkers / totalCapacity) * 100 : 0,
    conflicts,
    mukkadamsOnLeave: mukkadamsOnLeaveIds.length,
  };
};

const [prefillData, setPrefillData] = useState<{jobId: string, activityId: number} | null>(null);

// 2. Define the function
const handleStartAllocation = (jobId: string, activityId: number) => {
  // Save the specific job and activity IDs to pre-fill the form
  setPrefillData({ jobId, activityId }); 
  
  // Close the current day details view
  setShowDayDetail(false); 
  
  // Open the allocation form
  // setShowAllocationModal(true); 
};


const fetchDayTotal = async (date: Date) => {
  const key = formatDate(date);
  if (dayTotals[key] != null) return;

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

useEffect(() => {
  // prefetch for current month
  days.forEach(d => { if (d) fetchDayTotal(d); });
}, [currentMonth]);

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
  // prefetch for current month
  days.forEach((d) => {
    if (d) fetchDayTotal(d);
  });
}, [currentMonth]);

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

  return (
    <div
      key={dateKey}
      className={`day-cell ${capacity.status} ${isSelected ? 'selected' : ''} ${hasOverload ? 'overload' : ''}`}
      onClick={() => handleDateClick(date)}
      onContextMenu={(e) => handleDateRightClick(e, date)}
    >
      {/* Header row */}
      <div className="day-header-row">
        <span className="day-number">{date.getDate()}</span>

        <div className="day-status-group">
          {/* Capacity ratio */}
          {capacity.status !== 'holiday' && capacity.status !== 'empty' && (
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
          {capacity.conflicts.length > 0 && (
            <span
              className="mini-conflict"
              title={`${capacity.conflicts.length} conflicts`}
            >
              ⚠️{capacity.conflicts.length}
            </span>
          )}
        </div>
      </div>

      {/* Holiday badge */}
      {capacity.status === 'holiday' && (
        <div className="capacity-badge holiday">🏖️ Holiday</div>
      )}

      {/* Jobs count – only in Jobs view */}
{/* Jobs count – only in Jobs view, exclude manually moved activities */}
{viewModes.includes('jobs') && dayJobs.length > 0 && (() => {
  const aiCount = dayJobs.reduce((sum, job) =>
    sum + (job.activities || []).filter(act =>
      !(act as any).is_manually_moved
    ).length, 0
  );
  return aiCount > 0 ? (
    <div className="capacity-badge jobs-badge">
      {aiCount} ai
    </div>
  ) : null;
})()}
      {/* Potential badge – show in Jobs + Potential views */}
      {/* {(viewMode === 'jobs' )  && (
        <div className="capacity-badge potential-badge">
          {dayPotential.length} potential
        </div>
      )} */}

      {(viewModes.includes('potential')) && hasPotential && (
        <div className="capacity-badge potential-badge">
          {dayPotential.length} potential
        </div>
      )}

      {/* Allocations count – only in Allocations view */}
{viewModes.includes('allocations') && (() => {
  // ✅ Count H activities from allJobs for this date
  // ✅ Use jobs (filtered) not allJobs so farmer/plot filters apply
const hCount = jobs.reduce((sum, job) =>
  sum + (job.activities || []).filter(act =>
    act.scheduled_date?.slice(0, 10) === dateKey &&
    (act as any).is_manually_moved === true
  ).length, 0
);

  return (
    <div className="allocation-chips">
      {hCount > 0 && (
        <div
          className="allocation-chip"
          style={{ backgroundColor: '#fff7ed', color: '#c2410c', fontWeight: 700 }}
        >
          {hCount} H
        </div>
      )}
      {/* ✅ Only show allocation count when NOT in jobs mode
      {!viewModes.includes('jobs') && dayAllocs.length > 0 && (
        <div className="allocation-chip more">+{dayAllocs.length}</div>
      )} */}
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
jobs={(allJobs || jobs).filter(job => {
  const dateStr = formatDate(detailDate);
  return (job.activities || []).some(a => a.scheduled_date?.slice(0, 10) === dateStr);
}).map(job => ({
  ...job,
  activities: (job.activities || []).filter(a => 
    a.scheduled_date?.slice(0, 10) === formatDate(detailDate)
  )
}))}
    allocations={getDayAllocations(detailDate)}
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

