// components/CalendarPanel.tsx
import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight,Users, Calendar as CalendarIcon, ChevronDown, Sprout, MapPin, Layers, Clock } from 'lucide-react';
import { Mukkadam, Allocation, Job } from '../types/types';
import LeaveModal from './leave';
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
  cropName: string;
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

interface CalendarFilters {
  farmerId: string | null;
  mukkadamId: number | null;
  dateFrom: string | null;
  dateTo: string | null;
  plotId: number | null;
  activityId: number | null;
  cropName: string | null;
  variety: string | null;
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
  viewModes: ('jobs' | 'allocations' | 'potential' | 'payments')[];
  jobsByDate?: Record<string, Job[]>;
  jobs: Job[];
  clusterId: number;
  overloadMap?: Record<string, any>;
  onStartAllocation: (jobId: string, activityId: number, activity: any) => void;
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
  const [showDayDetail, setShowDayDetail] = useState(false);
  const [detailDate, setDetailDate] = useState<Date | null>(null);
  const [detailCapacity, setDetailCapacity] = useState<any | null>(null);
  const [dayTotals, setDayTotals] = useState<Record<string, number>>({});
  const [availableMukkadamIds, setAvailableMukkadamIds] = useState<Set<number>>(new Set());

  const getDaysInMonth = () => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();

    const days: (Date | null)[] = [];

    for (let i = 0; i < startingDayOfWeek; i++) {
      days.push(null);
    }

    for (let day = 1; day <= daysInMonth; day++) {
      days.push(new Date(year, month, day));
    }

    return days;
  };

  const formatDate = (date: Date): string => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };

  const days = getDaysInMonth();

  const getDayAllocations = (date: Date | null) => {
    if (!date) return [];
    const dateStr = formatDate(date);

    const dayAllocations = allocations.filter(
      (a) => formatDate(new Date(a.allocated_date)) === dateStr,
    );

    return dayAllocations.filter((alloc) => {
      if (!filters?.activityId) return true;

      const job = (allJobs || jobs).find((j) => j.job_id === alloc.job_id);
      if (!job) return true;

      const activity = job.activities?.find((a) => a.id === alloc.job_activity);
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
    return Object.values(overloadMap).filter(
      (o: any) => o.scheduled_date === dateStr,
    );
  };

  const getDayHasCarryForward = (date: Date | null) => {
    if (!date) return false;
    const dateStr = formatDate(date);
    return allocations.some(
      (a) =>
        formatDate(new Date(a.allocated_date)) === dateStr &&
        (a as any).is_carry_forward === true,
    );
  };

  const fetchDayTotal = async (date: Date) => {
    const key = formatDate(date);
    if (dayTotals[key] != null) return;

    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadams/day_total_capacity/?date=${key}&cluster_id=${clusterId}`,
      );
      const data = await res.json();
      setDayTotals((prev) => ({ ...prev, [key]: data.total_capacity }));
    } catch (e) {
      console.error('Failed day total', e);
    }
  };

// 1. store per-date available ids
const [availableMukkadamIdsByDate, setAvailableMukkadamIdsByDate] =
  useState<Record<string, Set<number>>>({});

const fetchAvailableMukkadamsForDate = async (date: Date) => {
  const key = formatDate(date);
  if (availableMukkadamIdsByDate[key]) return;

  try {
    const res = await fetch(
      `${API_BASE_URL}/api/mukkadams/daily_capacity_all/?date=${key}&cluster_id=${clusterId}`,
    );
    const data = await res.json();
    const ids = new Set<number>(
      (data as any[])
        .filter((d) => d.available_crew_size > 0)
        .map((d) => d.mukkadam_id),
    );
    setAvailableMukkadamIdsByDate(prev => ({ ...prev, [key]: ids }));
  } catch (e) {
    console.error('Failed to fetch daily capacity_all', e);
  }
};

// 2. single effect
useEffect(() => {
  days.forEach((d) => {
    if (d) {
      fetchDayTotal(d);
      fetchAvailableMukkadamsForDate(d);
    }
  });
}, [currentMonth]);

  const usedWorkersByMukkadam = new Map<number, number>();
  allocations.forEach((a) => {
    if ((a as any).allows_second_job === true) return;
    const current = usedWorkersByMukkadam.get(a.mukkadam) || 0;
    usedWorkersByMukkadam.set(
      a.mukkadam,
      current + (a.allocated_workers || 0),
    );
  });

  const maxWorkMap = new Map<string, MaxWorkRow>();

  mukkadams.forEach((m) => {
    if (!availableMukkadamIds.has(m.mukkadam_id)) return;

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
  if (!date) {
    return {
      status: 'empty',
      used: 0,
      total: 0,
      percentage: 0,
      conflicts: [],
      mukkadamsOnLeave: 0,
      neededAc: 0,
      canDoAc: 0,
    };
  }

  const dateStr = formatDate(date);       // "2026-03-28"
  const dayAllocations = getDayAllocations(date);
  const dayLeaves = getDayLeaves(date);

  // 1) Holiday
  const generalHoliday = dayLeaves.find(
    (l) => l.leave_type === 'general',
  );
  if (generalHoliday) {
    return {
      status: 'holiday',
      used: 0,
      total: 0,
      percentage: 0,
      conflicts: [],
      reason: generalHoliday.reason || 'General Holiday',
      mukkadamsOnLeave: 0,
      neededAc: 0,
      canDoAc: 0,
    };
  }

  // 2) Leaves per mukkadam
  const leaveByMukkadam = new Map<number, number>();
  dayLeaves
    .filter((l) => l.leave_type === 'mukkadam')
    .forEach((l) => {
      const id = l.mukkadam;
      leaveByMukkadam.set(
        id,
        (leaveByMukkadam.get(id) || 0) + (l.crew_on_leave || 0),
      );
    });
  const mukkadamsOnLeaveIds = Array.from(leaveByMukkadam.keys());

  // 3) Needed acres today (same as neededAcToday in DayDetail)
  const jobsSource = allJobs || jobs;

  const neededAcToday = jobsSource.reduce((sum, job) => {
    const forJob = (job.activities || []).reduce((s, act: any) => {
      if (act.scheduled_date?.slice(0, 10) !== dateStr) return s;

      const total = Number(act.total_area || 0);
      const allocatedHere = dayAllocations
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
    }, 0);
    return sum + forJob;
  }, 0);

  // 4) Available mukkadams for this date
  const availableIdsForDate =
    availableMukkadamIdsByDate?.[dateStr] || new Set<number>();

  // workers already allocated on this day, per mukkadam
  const usedWorkersByMukkadam = new Map<number, number>();
  dayAllocations.forEach((a: any) => {
    if (a.allows_second_job === true) return; // half‑day still free
    const current = usedWorkersByMukkadam.get(a.mukkadam) || 0;
    usedWorkersByMukkadam.set(
      a.mukkadam,
      current + (a.allocated_workers || 0),
    );
  });

  // map of mukkadamId -> has any half‑day allocation on this date
  const hasHalfDayByMukkadam = new Map<number, boolean>();
  dayAllocations.forEach((a: any) => {
    if (a.allows_second_job === true) {
      hasHalfDayByMukkadam.set(a.mukkadam, true);
    }
  });

  // 5) Can‑do acres today (same formula as canDoAcToday)
  let canDoAcToday = 0;
  mukkadams.forEach((m: any) => {
    if (!availableIdsForDate.has(m.mukkadam_id)) return;

    const baseCrew =
      (m as any).available_crew_size ?? m.crew_size ?? 0;
    const used = usedWorkersByMukkadam.get(m.mukkadam_id) || 0;
    const remainingWorkers = Math.max(baseCrew - used, 0);
    if (remainingWorkers <= 0) return;

    const bestProd = (m.activity_rates || []).reduce(
      (best: number, rate: any) => {
        const p = Number(rate.productivity_per_worker || 0);
        return p > best ? p : best;
      },
      0,
    );
    if (bestProd <= 0) return;

    const hasHalfDay = hasHalfDayByMukkadam.get(m.mukkadam_id) === true;
    let maxAc = remainingWorkers * bestProd;
    if (hasHalfDay) {
      maxAc = maxAc * 0.6; // same 40% reduction
    }

    canDoAcToday += maxAc;
  });

  // 6) Worker usage vs capacity (optional, keep for tooltip)
  const totalCapacity =
    dayTotals[dateStr] ??
    Array.from(usedWorkersByMukkadam.values()).reduce(
      (s, v) => s + v,
      0,
    );
  const usedWorkers = dayAllocations.reduce(
    (sum, a) => sum + a.allocated_workers,
    0,
  );
  const percentage =
    totalCapacity > 0 ? (usedWorkers / totalCapacity) * 100 : 0;

  // 7) Status from acres:
  //    RED     if neededAcToday > canDoAcToday
  //    YELLOW  if not red but >= 60% workers used
  //    GREEN   otherwise
  //    EMPTY   if no capacity and no usage
  let status: 'good' | 'warning' | 'caution' | 'empty' | 'error' =
    'good';

  if (totalCapacity === 0 && usedWorkers === 0) {
    status = 'empty';
  } else if (neededAcToday > canDoAcToday + 1e-6) {
    status = 'error'; // RED
  } else if (percentage >= 60) {
    status = 'warning'; // YELLOW
  } else {
    status = 'good'; // GREEN
  }

  console.log('DAY CAP', dateStr, {
    neededAcToday,
    canDoAcToday,
    status,
    percentage,
  });

  return {
    status,
    used: usedWorkers,
    total: totalCapacity,
    percentage,
    conflicts: [], // not using per-mukkadam conflicts here
    neededAc: neededAcToday,
    canDoAc: canDoAcToday,
    mukkadamsOnLeave: mukkadamsOnLeaveIds.length,
  };
};


  useEffect(() => {
    days.forEach((d) => {
      if (d) fetchDayTotal(d);
    });
  }, [currentMonth]);

  const handlePrevMonth = () => {
    const newDate = new Date(
      currentMonth.getFullYear(),
      currentMonth.getMonth() - 1,
      1,
    );
    onMonthChange(newDate);
  };

  const handleNextMonth = () => {
    const newDate = new Date(
      currentMonth.getFullYear(),
      currentMonth.getMonth() + 1,
      1,
    );
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

  const handleDateRightClick = (
    e: React.MouseEvent,
    date: Date | null,
  ) => {
    e.preventDefault();
    if (!date) return;
    setLeaveModalDate(date);
    setShowLeaveModal(true);
  };

  const handleAllocationDateChange = async (allocation: Allocation) => {
    const newDateStr = window.prompt(
      'Move this allocation to date (YYYY-MM-DD):',
      allocation.allocated_date,
    );
    if (!newDateStr || newDateStr === allocation.allocated_date) return;

    try {
      const leaveResponse = await fetch(
        `${API_BASE_URL}/api/leaves/?start_date=${newDateStr}&end_date=${newDateStr}&cluster_id=${clusterId}`,
      );
      const leaves = await leaveResponse.json();

      const generalHoliday = leaves.find(
        (l: any) =>
          l.date === newDateStr &&
          l.leave_type === 'general' &&
          l.is_active,
      );

      if (generalHoliday) {
        alert(
          `Cannot move allocation to this date: ${
            generalHoliday.reason || 'General Holiday'
          }`,
        );
        return;
      }
    } catch (error) {
      console.error('Failed to check holiday status:', error);
      alert('Failed to verify target date. Please try again.');
      return;
    }

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


  // Acres for a given day: planned from jobs vs allocated from allocations
const getDayAcreSummary = (date: Date) => {
  const dateStr = formatDate(date);

  let planned = 0;
  (allJobs || jobs).forEach((job) => {
    (job.activities || []).forEach((act: any) => {
      if (act.scheduled_date?.slice(0, 10) === dateStr) {
        planned += Number(act.total_area || 0);
      }
    });
  });

  let allocated = 0;
  getDayAllocations(date).forEach((a) => {
    allocated += Number((a as any).allocated_area || 0);
  });

  return { planned, allocated };
};

// Slots for a given day: allows_second_job=false => 2 slots, true => 1 slot,
// but extra half‑day for same (mukkadam, job_id) does NOT add more slots.
const getDaySlots = (date: Date) => {
  const dayAllocations = getDayAllocations(date) as any[];

  // --- USED SLOTS ----------------------------------------------------
  // group by (mukkadam, job_id)
  const byKey = new Map<string, any[]>();
  dayAllocations.forEach((a) => {
    const key = `${a.mukkadam}-${a.job_id}`;
    const arr = byKey.get(key) || [];
    arr.push(a);
    byKey.set(key, arr);
  });

  let usedSlots = 0;

  byKey.forEach((list) => {
    // each allocation contributes:
    // false => 2 slots, true => 1 slot, but cap per (mukkadam, job_id) is 2 slots
    let slotsForJob = 0;

    list.forEach((a) => {
      const add = a.allows_second_job === true ? 1 : 2;
      slotsForJob += add;
    });

    if (slotsForJob > 2) slotsForJob = 2; // cap per job/team pair
    usedSlots += slotsForJob;
  });

  // --- TOTAL SLOTS ---------------------------------------------------
  // all available mukkadams for that date from daily_capacity_all
  // availableMukkadamIds is already a Set<number> for the month,
  // but we must recalc per day: who actually has available_crew_size > 0 that day.
  // You already did this in fetchAvailableMukkadamsForDate(date), called in useEffect.
  // So for this date, all mukkadams in availableMukkadamIds are "available teams".

const availableTeamsCount = mukkadams.filter((m) =>
  (availableMukkadamIdsByDate[formatDate(date)] || new Set()).has(m.mukkadam_id),
).length;

  const totalSlots = availableTeamsCount * 2;

  return { usedSlots, totalSlots };
};

  return (
    <div className="w-full h-full flex flex-col bg-stone-50">
      {/* Top header bar */}

<div className="px-4 py-3 border-b border-stone-200 bg-white">
  {/* Month + prev/next */}
  <div className="flex items-center justify-between mb-2">
    <div className="flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-xl bg-emerald-50 flex items-center justify-center border border-emerald-100 text-emerald-600">
        <CalendarIcon size={16} />
      </div>
      <div>
        <h2 className="text-sm font-semibold text-stone-800">
          {currentMonth.toLocaleDateString('en-US', {
            month: 'long',
            year: 'numeric',
          })}
        </h2>
        <p className="text-xs text-stone-400">
          Click a day to see jobs, allocations and capacity
        </p>
      </div>
    </div>

    <div className="flex items-center gap-1.5">
      <button
        className="w-7 h-7 rounded-lg border border-stone-200 flex items-center justify-center hover:bg-stone-50 hover:shadow-sm"
        onClick={handlePrevMonth}
      >
        <ChevronLeft size={14} className="text-stone-500" />
      </button>
      <button
        className="w-7 h-7 rounded-lg border border-stone-200 flex items-center justify-center hover:bg-stone-50 hover:shadow-sm"
        onClick={handleNextMonth}
      >
        <ChevronRight size={14} className="text-stone-500" />
      </button>
    </div>
  </div>

  {/* Filters row – same style as FarmDashboard */}
  <div className="flex items-center gap-1.5 flex-wrap">
    {/* status pills control viewModes */}
    {[
      ['ai', 'AI', 'jobs'],
      ['h', 'Reviewed', 'allocations'],
      ['alloc', 'Allocated', 'allocations'],
    ].map(([value, label, mode]) => {
      const active = viewModes.includes(mode as any);
      const dotColor =
        value === 'ai'
          ? 'bg-violet-500'
          : value === 'h'
          ? 'bg-amber-400'
          : 'bg-emerald-500';
      return (
        <button
          key={value}
          onClick={() => {
            // simple toggle for that mode
            setFilters(prev => ({ ...prev })); // no-op; keep API
            // you likely have setter for viewModes in parent;
            // if not, call a callback via props instead.
          }}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap ${
            active
              ? 'bg-emerald-600 text-white'
              : 'border border-stone-200 bg-white text-stone-600 hover:border-emerald-300'
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              active ? 'bg-white' : dotColor
            }`}
          />
          {label}
        </button>
      );
    })}

    <div className="w-px h-5 bg-stone-200 mx-1" />

    {/* entity filters – wired to CalendarFilters */}
    <button
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-stone-200 bg-white text-xs font-medium text-stone-600 hover:border-emerald-300 transition-all whitespace-nowrap"
      onClick={() =>
        setFilters(prev => ({
          ...prev,
          farmerId: null, // open dropdown in future; for now just clear
        }))
      }
    >
      <Users size={12} className="opacity-50" />
      Farmers
      <ChevronDown size={10} className="opacity-30" />
    </button>

    <button
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-stone-200 bg-white text-xs font-medium text-stone-600 hover:border-emerald-300 transition-all whitespace-nowrap"
      onClick={() =>
        setFilters(prev => ({
          ...prev,
          cropName: null,
        }))
      }
    >
      <Sprout size={12} className="opacity-50" />
      Crops
      <ChevronDown size={10} className="opacity-30" />
    </button>

    <button
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-stone-200 bg-white text-xs font-medium text-stone-600 hover:border-emerald-300 transition-all whitespace-nowrap"
      onClick={() =>
        setFilters(prev => ({
          ...prev,
          mukkadamId: null,
        }))
      }
    >
      <Users size={12} className="opacity-50" />
      Teams
      <ChevronDown size={10} className="opacity-30" />
    </button>

    {/* optionally more filters like in FarmDashboard */}
    {/* Plots */}
    <button
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-stone-200 bg-white text-xs font-medium text-stone-600 hover:border-emerald-300 transition-all whitespace-nowrap"
      onClick={() =>
        setFilters(prev => ({
          ...prev,
          plotId: null,
        }))
      }
    >
      <MapPin size={12} className="opacity-50" />
      Plots
      <ChevronDown size={10} className="opacity-30" />
    </button>

    {/* Varieties */}
    <button
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-stone-200 bg-white text-xs font-medium text-stone-600 hover:border-emerald-300 transition-all whitespace-nowrap"
      onClick={() =>
        setFilters(prev => ({
          ...prev,
          variety: null,
        }))
      }
    >
      <Layers size={12} className="opacity-50" />
      Varieties
      <ChevronDown size={10} className="opacity-30" />
    </button>

    {/* Activities */}
    <button
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-stone-200 bg-white text-xs font-medium text-stone-600 hover:border-emerald-300 transition-all whitespace-nowrap"
      onClick={() =>
        setFilters(prev => ({
          ...prev,
          activityId: null,
        }))
      }
    >
      <Clock size={12} className="opacity-50" />
      Activities
      <ChevronDown size={10} className="opacity-30" />
    </button>
  </div>
</div>

      {/* Calendar grid container */}
      <div className="flex-1 px-4 py-3">
        <div className="grid grid-cols-7 gap-1 text-xs font-medium text-stone-400 mb-1">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
            <div
              key={day}
              className="px-2 py-1 text-center uppercase tracking-wide"
            >
              {day}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-1 auto-rows-[minmax(86px,1fr)]">
{days.map((date, index) => {
  if (!date) {
    return (
      <div
        key={`empty-${index}`}
        className="rounded-xl border border-dashed border-stone-200 bg-stone-50/50"
      />
    );
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

  const acreSummary = getDayAcreSummary(date);
  const slotSummary = getDaySlots(date);

  const aiCount =
    viewModes.includes('jobs') && dayJobs.length > 0
      ? dayJobs.reduce(
          (sum, job) =>
            sum +
            (job.activities || []).filter(
              (act) => !(act as any).is_manually_moved,
            ).length,
          0,
        )
      : 0;


 let totalAi = 0;
let activeAi = 0;
let movedAi = 0;

if (viewModes.includes('jobs') && dayJobs.length > 0) {
  dayJobs.forEach((job) => {
    (job.activities || []).forEach((act: any) => {
      const isAi = (act as any).is_manually_moved !== true;
      if (!isAi) return;

      const scheduledDate = act.scheduled_date?.slice(0, 10);
      if (scheduledDate !== dateKey) return;

      totalAi += 1;

      const totalPlanned = Number(
        act.total_area ?? (act as any).total_area ?? 0,
      );

      const allocatedOnThisDay = getDayAllocations(date)
        .filter(
          (a) =>
            a.job_id === job.job_id &&
            a.job_activity === act.id,
        )
        .reduce(
          (sum, a) => sum + Number((a as any).allocated_area || 0),
          0,
        );

      const remainingForDay = totalPlanned - allocatedOnThisDay;

      if (remainingForDay > 0) {
        activeAi += 1;          // still has acres on this day
      } else {
        movedAi += 1;           // fully allocated => "moved"
      }
    });
  });
}


  let hCount = 0;
  if (viewModes.includes('allocations')) {
    hCount = jobs.reduce(
      (sum, job) =>
        sum +
        (job.activities || []).filter(
          (act) =>
            act.scheduled_date?.slice(0, 10) === dateKey &&
            (act as any).is_manually_moved === true,
        ).length,
      0,
    );
  }

  const carryForwardCount = dayAllocs.filter(
    (a) => (a as any).is_carry_forward,
  ).length;
  const normalAllocCount = dayAllocs.filter(
    (a) => !(a as any).is_carry_forward,
  ).length;

  const statusRing =
    capacity.status === 'holiday'
      ? 'border-amber-300 bg-amber-50/70'
      : capacity.status === 'error' || hasOverload
      ? 'border-red-300 bg-red-50/60'
      : capacity.status === 'warning'
      ? 'border-amber-300 bg-amber-50/60'
      : capacity.status === 'caution'
      ? 'border-emerald-200 bg-emerald-50/60'
      : capacity.status === 'empty'
      ? 'border-stone-200 bg-white'
      : 'border-emerald-200 bg-emerald-50/40';

  const selectedRing = isSelected
    ? 'ring-2 ring-emerald-500 ring-offset-1 ring-offset-stone-50'
    : '';

  const cfRing = hasCarryForward
    ? 'shadow-[0_0_0_1px_rgba(124,58,237,0.45)]'
    : '';

  return (
    <button
      key={dateKey}
      type="button"
      onClick={() => handleDateClick(date)}
      onContextMenu={(e) => handleDateRightClick(e, date)}
        className={[
    'relative flex flex-col rounded-2xl border px-2.5 py-2 text-left transition-colors duration-150',
    'hover:bg-stone-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500',
    statusRing,
    selectedRing,
    cfRing,
  ]
    .filter(Boolean)
    .join(' ')}

    >
      {/* Top row: date + mini metrics */}
      <div className="flex items-start justify-between gap-1">
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-stone-800 leading-none">
            {date.getDate()}
          </span>
          <span className="mt-1 inline-flex items-center rounded-full bg-white/70 px-1.5 py-0.5 text-[10px] font-medium text-stone-400 border border-stone-100">
            {capacity.status === 'holiday'
              ? 'Holiday'
              : ''}
          </span>
        </div>

        <div className="flex flex-col items-end gap-0.5">
          {capacity.status !== 'holiday' && capacity.status !== 'empty' && (
            <span className="inline-flex items-center gap-1 rounded-full bg-white/80 border border-stone-100 px-1.5 py-0.5 text-[10px] font-semibold text-stone-700">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500" />
              {capacity.total}w
            </span>
          )}

          {capacity.mukkadamsOnLeave > 0 && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-sky-50 border border-sky-100 px-1.5 py-0.5 text-[10px] font-medium text-sky-700"
              title={`${capacity.mukkadamsOnLeave} mukkadams on leave`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500" />
              {capacity.mukkadamsOnLeave} on leave
            </span>
          )}

          {/* {capacity.conflicts.length > 0 && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-red-50 border border-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-600 mt-0.5"
              title={`${capacity.conflicts.length} overload conflicts`}
            >
              ⚠︎ {capacity.conflicts.length}
            </span>
          )} */}
        </div>
      </div>

      {capacity.status === 'holiday' && (
        <div className="mt-2 inline-flex items-center gap-1 rounded-lg bg-amber-100 px-2 py-1 text-[11px] font-medium text-amber-800">
          🏖️ Holiday
          {capacity.reason && (
            <span className="ml-1 text-[10px] font-normal text-amber-700 truncate max-w-[80px]">
              • {capacity.reason}
            </span>
          )}
        </div>
      )}

      {/* Middle badges row (AI jobs, potential, allocations) */}
      <div className="mt-2 flex flex-wrap gap-1">
{viewModes.includes('jobs') && totalAi > 0 && (
  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200 px-2 py-0.5 text-[11px] font-semibold">
    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
    {movedAi === 0
      ? `${totalAi} AI`                          // nothing moved
      : movedAi === totalAi
      ? `${movedAi} of ${totalAi} moved`         // all moved (your 1 of 1 moved)
      : `${activeAi} of ${totalAi} AI`}         
  </span>
)}


        {viewModes.includes('potential') && hasPotential && (
          <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 text-violet-700 border border-violet-200 px-2 py-0.5 text-[11px] font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
            {dayPotential.length} potential
          </span>
        )}

        {viewModes.includes('allocations') &&
          (hCount > 0 || normalAllocCount > 0 || carryForwardCount > 0) && (
            <div className="flex flex-wrap gap-1">
              {hCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 text-orange-700 border border-orange-200 px-2 py-0.5 text-[11px] font-semibold">
                  {hCount} H
                </span>
              )}
              {normalAllocCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 text-sky-700 border border-sky-200 px-2 py-0.5 text-[11px] font-semibold">
                  {normalAllocCount} alloc
                </span>
              )}
              {carryForwardCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 text-violet-800 border border-violet-200 px-2 py-0.5 text-[11px] font-semibold">
                  🔄 {carryForwardCount} CF
                </span>
              )}
            </div>
          )}
      </div>

      {/* Acre progress bar + slots */}
      <div className="mt-auto pt-1">
        {acreSummary.planned > 0 && (
          <div className="w-full h-1.5 rounded-full bg-emerald-100 overflow-hidden">
            <div
              className={[
                'h-1.5 rounded-full transition-all duration-200',
                acreSummary.allocated > acreSummary.planned
                  ? 'bg-red-500'
                  : 'bg-emerald-500',
              ].join(' ')}
              style={{
                width: `${Math.min(
                  (acreSummary.allocated /
                    (acreSummary.planned || 1)) *
                    100,
                  120,
                )}%`,
              }}
            />
          </div>
        )}

        <div className="mt-0.5 flex items-center justify-between text-[10px] tabular-nums">
          <span
            className={
              acreSummary.allocated > acreSummary.planned
                ? 'text-red-600 font-semibold'
                : 'text-stone-400'
            }
          >
            {acreSummary.allocated.toFixed(1)}/
            {acreSummary.planned.toFixed(1)}ac
          </span>
          {slotSummary.totalSlots > 0 && (
            <span className="text-stone-300">
              {slotSummary.usedSlots}/{slotSummary.totalSlots} slots
            </span>
          )}
        </div>
      </div>

      {isSelected && (
        <div className="pt-0.5 flex items-center justify-between text-[10px] text-stone-400">
          <span>Click for day details</span>
          {hasCarryForward && (
            <span className="inline-flex items-center gap-1 text-violet-600">
              <span className="w-1 h-1 rounded-full bg-violet-500" />
              carry forward
            </span>
          )}
        </div>
      )}
    </button>
  );
})}

        </div>
      </div>

      {/* Leave Modal */}
      {showLeaveModal && (
        <LeaveModal
          selectedDate={leaveModalDate}
          mukkadams={mukkadams}
          existingLeaves={leaves.filter(
            (l) => l.date === formatDate(leaveModalDate),
          )}
          onClose={() => setShowLeaveModal(false)}
          onLeaveMarked={onLeavesUpdated}
          clusterId={clusterId}
        />
      )}

      {/* Day Detail Modal */}
      {showDayDetail && detailDate && detailCapacity && (
        <DayDetailModal
          date={detailDate}
          jobs={jobs
            .filter((job) => {
              const dateStr = formatDate(detailDate);
              const hasScheduledActivity = (job.activities || []).some(
                (a) => a.scheduled_date?.slice(0, 10) === dateStr,
              );
              const hasAllocationOnDate = getDayAllocations(
                detailDate,
              ).some((a) => a.job_id === job.job_id);
              return hasScheduledActivity || hasAllocationOnDate;
            })
            .map((job) => ({
              ...job,
              activities: (job.activities || []).filter((a) => {
                const dateStr = formatDate(detailDate);
                const scheduledMatch =
                  a.scheduled_date?.slice(0, 10) === dateStr;
                const hasAlloc = getDayAllocations(detailDate).some(
                  (alloc) =>
                    alloc.job_id === job.job_id &&
                    alloc.job_activity === a.id,
                );
                return scheduledMatch || hasAlloc;
              }),
            }))}
          allocations={getDayAllocations(detailDate)}
          mukkadams={mukkadams}
          capacitySummary={detailCapacity}
          leaves={getDayLeaves(detailDate)}
          overloads={getDayOverloads(detailDate)}
          onClose={() => setShowDayDetail(false)}
          onAllocationDateChange={(job, allocation) =>
            handleAllocationDateChange(allocation)
          }
          onAllocationDelete={handleAllocationDelete}
          onStartAllocation={onStartAllocation}
          potentialJobs={
            potentialByDate?.[formatDate(detailDate)] || []
          }
          filters={filters}
          allJobs={allJobs || jobs}
          viewMode={viewModes}
          clusterId={clusterId}
        />
      )}
    </div>
  );
};

export default CalendarPanel;
