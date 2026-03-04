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
          window.location.reload();
    
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
            window.location.reload();
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
// ─────────────────────────────────────────────────────────────────────────────
// DROP-IN REPLACEMENT for calculateDayCapacity inside CalendarPanel.tsx
//
// KEY FIX: When there are 0 allocations but scheduled job-activities exist,
// run the "1 mukkadam = 1 activity" feasibility check against the JOB data
// (not just allocations). This catches the case where 2 activities are
// AI-scheduled for the same day but only 1 mukkadam is suggested.
// ─────────────────────────────────────────────────────────────────────────────

const calculateDayCapacity = (date: Date | null) => {
  if (!date)
    return { status: 'empty', used: 0, total: 0, percentage: 0, conflicts: [], mukkadamsOnLeave: 0 };

  const dateStr = formatDate(date);
  const dayAllocations = getDayAllocations(date);
  const dayLeaves = getDayLeaves(date);

  // ── 1. General holiday ────────────────────────────────────────────────────
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

  // ── 2. Per-mukkadam leave counts ──────────────────────────────────────────
  const leaveByMukkadam = new Map<number, number>();
  dayLeaves
    .filter((l) => l.leave_type === 'mukkadam')
    .forEach((l) => {
      const id = l.mukkadam;
      leaveByMukkadam.set(id, (leaveByMukkadam.get(id) || 0) + (l.crew_on_leave || 0));
    });

  const mukkadamsOnLeaveIds = Array.from(leaveByMukkadam.keys());

  const conflicts: any[] = [];

  // ── 3A. ALLOCATION-BASED check (when allocations exist) ──────────────────
  if (dayAllocations.length > 0) {
    const activityNames: string[] = [
      ...new Set(dayAllocations.map((a) => a.activity_name)),
    ];

    const referencedMukkadamIds: number[] = [
      ...new Set(dayAllocations.map((a) => a.mukkadam)),
    ];

    const availableMukkadams = referencedMukkadamIds
      .map((id) => mukkadams.find((m) => m.mukkadam_id === id))
      .filter(Boolean)
      .filter((m) => {
        const leaveCount = leaveByMukkadam.get(m!.mukkadam_id) || 0;
        return m!.crew_size - leaveCount > 0;
      })
      .map((m) => ({
        mukkadam: m!,
        canDo: new Set<string>(
          (m!.activity_rates || []).map((r: any) => r.activity_name as string)
        ),
      }));

    // Activities with no capable mukkadam
    const uncoverable = activityNames.filter(
      (act) => !availableMukkadams.some((am) => am.canDo.has(act))
    );
    uncoverable.forEach((act) => {
      conflicts.push({
        type: 'no_capable_mukkadam',
        activity: act,
        message: `No available mukkadam can perform "${act}"`,
      });
    });

    // More activities than mukkadams
    if (activityNames.length > availableMukkadams.length) {
      conflicts.push({
        type: 'activity_overload',
        activitiesCount: activityNames.length,
        mukkadamsCount: availableMukkadams.length,
        message: `${activityNames.length} activities but only ${availableMukkadams.length} mukkadam team(s) — each team does 1 activity only`,
      });
    } else if (uncoverable.length === 0) {
      // Greedy assignment check
      const sorted = [...activityNames].sort(
        (a, b) =>
          availableMukkadams.filter((am) => am.canDo.has(a)).length -
          availableMukkadams.filter((am) => am.canDo.has(b)).length
      );

      const assignedMukkadamIds = new Set<number>();
      const unassigned: string[] = [];

      for (const act of sorted) {
        const candidate = availableMukkadams.find(
          (am) =>
            am.canDo.has(act) &&
            !assignedMukkadamIds.has(am.mukkadam.mukkadam_id)
        );
        if (candidate) {
          assignedMukkadamIds.add(candidate.mukkadam.mukkadam_id);
        } else {
          unassigned.push(act);
        }
      }

      unassigned.forEach((act) => {
        conflicts.push({
          type: 'assignment_conflict',
          activity: act,
          message: `Cannot assign a free mukkadam to "${act}" — all capable teams already occupied`,
        });
      });
    }

    // Same mukkadam assigned to multiple activities
    const mukkadamActivities = new Map<number, string[]>();
    dayAllocations.forEach((alloc) => {
      if (!mukkadamActivities.has(alloc.mukkadam))
        mukkadamActivities.set(alloc.mukkadam, []);
      if (!mukkadamActivities.get(alloc.mukkadam)!.includes(alloc.activity_name))
        mukkadamActivities.get(alloc.mukkadam)!.push(alloc.activity_name);
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

  } else {
    // ── 3B. JOB-BASED check (no allocations yet — AI scheduled activities) ──
    // Collect all non-manually-moved activities scheduled for this date
    const scheduledActivities = (allJobs || jobs).flatMap((job) =>
      (job.activities || []).filter(
        (act) =>
          act.scheduled_date?.slice(0, 10) === dateStr &&
          !(act as any).is_manually_moved
      ).map((act) => ({
        activityName: act.activity_name as string,
        // suggested mukkadam ids — stored as recommended_mukkadam_id or similar
        // Check common field names your API might return:
        suggestedMukkadamId:
          (act as any).recommended_mukkadam_id ??
          (act as any).suggested_mukkadam ??
          (act as any).mukkadam_id ??
          null,
      }))
    );

    if (scheduledActivities.length > 0) {
      // Distinct activity types scheduled today
      const distinctActivities = [...new Set(scheduledActivities.map((a) => a.activityName))];

      // Distinct mukkadams suggested for today's activities
      const suggestedMukkadamIds = [
        ...new Set(
          scheduledActivities
            .map((a) => a.suggestedMukkadamId)
            .filter((id): id is number => id != null)
        ),
      ];

      // Available mukkadams from the full cluster mukkadams list
      // Filter out those fully on leave
      const availableClusterMukkadams = mukkadams.filter((m) => {
        const leaveCount = leaveByMukkadam.get(m.mukkadam_id) || 0;
        return m.crew_size - leaveCount > 0;
      });

      // If we have suggested mukkadams, use them; otherwise fall back to cluster
      const effectiveMukkadams =
        suggestedMukkadamIds.length > 0
          ? availableClusterMukkadams.filter((m) =>
              suggestedMukkadamIds.includes(m.mukkadam_id)
            )
          : availableClusterMukkadams;

      // Core rule: activities > available mukkadams → RED
      if (distinctActivities.length > effectiveMukkadams.length) {
        conflicts.push({
          type: 'activity_overload',
          activitiesCount: distinctActivities.length,
          mukkadamsCount: effectiveMukkadams.length,
          message: `${distinctActivities.length} activities scheduled but only ${effectiveMukkadams.length} mukkadam team(s) available — each team does 1 activity only`,
        });
      } else if (effectiveMukkadams.length > 0) {
        // Greedy capability check using job-level activity names
        const availWithCap = effectiveMukkadams.map((m) => ({
          mukkadam: m,
          canDo: new Set<string>(
            (m.activity_rates || []).map((r: any) => r.activity_name as string)
          ),
        }));

        const uncoverable = distinctActivities.filter(
          (act) => !availWithCap.some((am) => am.canDo.has(act))
        );
        uncoverable.forEach((act) => {
          conflicts.push({
            type: 'no_capable_mukkadam',
            activity: act,
            message: `No available mukkadam can perform "${act}"`,
          });
        });

        if (uncoverable.length === 0) {
          const sorted = [...distinctActivities].sort(
            (a, b) =>
              availWithCap.filter((am) => am.canDo.has(a)).length -
              availWithCap.filter((am) => am.canDo.has(b)).length
          );

          const assignedIds = new Set<number>();
          const unassigned: string[] = [];

          for (const act of sorted) {
            const candidate = availWithCap.find(
              (am) => am.canDo.has(act) && !assignedIds.has(am.mukkadam.mukkadam_id)
            );
            if (candidate) {
              assignedIds.add(candidate.mukkadam.mukkadam_id);
            } else {
              unassigned.push(act);
            }
          }

          unassigned.forEach((act) => {
            conflicts.push({
              type: 'assignment_conflict',
              activity: act,
              message: `Cannot assign a free mukkadam to "${act}" — all capable teams already occupied`,
            });
          });
        }
      }
    }
  }

  // ── 4. Worker-hour utilisation (for warning/caution) ─────────────────────
  let totalUsedPercentage = 0;
  const referencedMukkadamIds: number[] = [
    ...new Set(dayAllocations.map((a) => a.mukkadam)),
  ];

  referencedMukkadamIds.forEach((id) => {
    const mukkadam = mukkadams.find((m) => m.mukkadam_id === id);
    if (!mukkadam) return;
    const leaveCount = leaveByMukkadam.get(id) || 0;
    const effectiveCrew = Math.max(mukkadam.crew_size - leaveCount, 0);

    dayAllocations
      .filter((a) => a.mukkadam === id)
      .forEach((alloc) => {
        const activityRate = mukkadam.activity_rates?.find(
          (r: any) => r.activity_name === alloc.activity_name
        );
        const efficiency = activityRate?.productivity_per_worker || 0.15;
        const maxCapacity = effectiveCrew * efficiency;
        const usagePercent = maxCapacity > 0 ? (alloc.allocated_area / maxCapacity) * 100 : 0;
        totalUsedPercentage += usagePercent;
      });
  });

  // ── 5. Final status ───────────────────────────────────────────────────────
  let status: 'good' | 'warning' | 'caution' | 'error' | 'empty' = 'good';

  if (conflicts.length > 0) {
    status = 'error';
  } else if (totalUsedPercentage >= 90) {
    status = 'warning';
  } else if (totalUsedPercentage >= 70) {
    status = 'caution';
  }

  const totalCapacity = dayTotals[dateStr] ?? 0;
  const usedWorkers = dayAllocations.reduce((sum, a) => sum + a.allocated_workers, 0);

  if (dayAllocations.length === 0 && totalCapacity === 0 && conflicts.length === 0) {
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

