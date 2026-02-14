import React, { useMemo, useState } from 'react';
import dayjs, { Dayjs } from 'dayjs';
import { ChevronLeft, ChevronRight, TrendingUp, DollarSign } from 'lucide-react';

type Allocation = {
  allocation_id: number;
  work_date: string;
  allocated_area: number;
  mukkadam_name: string | null;
  crew_size: number;
  mukkadam_price: number;
  transport_price: number;
  own_transport_price: number;
  total_cost: number;
  status: string;
  payment_request?: {
    status: string;
    requested_amount: number;
    requested_at?: string | null;
    paid_at?: string | null;
  } | null;
  transport_payment_request?: {
    status: string;
    requested_amount: number;
    requested_at?: string | null;
    paid_at?: string | null;
  } | null;
};

type FarmerPaymentsSummary = {
  total_expected: number;
  total_paid: number;
  total_pending: number;
  completion_percentage: number;
};

type Activity = {
  activity_id: string;
  activity_name: string;
  location: string;
  scheduled_date: string;
  total_area: number;
  allocated_area: number;
  remaining_area: number;
  rate_per_acre: number;
  total_price: number;
  subtotal: number;
  allocation_status: string;
  allocations: Allocation[];
  farmer_payments: FarmerPaymentsSummary | null;
};

type Job = {
  id: string;
  work_id: string;
  farmer_id: string;
  farmer?: {
    farmer_name: string;
    village: string;
  } | null;
  booking_type: 'TENDER' | 'ON_DEMAND' | null;
  status: string;
  activities: Activity[];
};

type Props = {
  jobs: Job[];
};

type DayAggregate = {
  date: string;
  jobs: Job[];
  activities: { job: Job; activity: Activity }[];
  farmer_expected: number;
  mukkadam_cost: number;
  total_area: number;
  allocated_area: number;
  tender_count: number;
  ondemand_count: number;
  allocation_count: number; // ✅ NEW
};

export const MonthTenderCalendar: React.FC<Props> = ({ jobs }) => {
  const [currentMonth, setCurrentMonth] = useState<Dayjs>(() =>
    dayjs().startOf('month')
  );
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const dayMap: Record<string, DayAggregate> = useMemo(() => {
    const map: Record<string, DayAggregate> = {};

    for (const job of jobs) {
      const bookingType = (job.booking_type || '').toUpperCase();

      for (const activity of job.activities || []) {
        const date = activity.scheduled_date;
        if (!date) continue;

        if (!map[date]) {
          map[date] = {
            date,
            jobs: [],
            activities: [],
            farmer_expected: 0,
            mukkadam_cost: 0,
            total_area: 0,
            allocated_area: 0,
            tender_count: 0,
            ondemand_count: 0,
            allocation_count: 0, // ✅ NEW
          };
        }

        const agg = map[date];

        agg.activities.push({ job, activity });
        if (!agg.jobs.includes(job)) {
          agg.jobs.push(job);
          if (bookingType === 'TENDER') agg.tender_count += 1;
          else if (bookingType === 'ON_DEMAND') agg.ondemand_count += 1;
        }

        agg.farmer_expected += activity.subtotal || activity.total_price || 0;

        // ✅ Count allocations for this date
        for (const alloc of activity.allocations || []) {
          if (alloc.work_date === date) {
            agg.mukkadam_cost += alloc.total_cost || 0;
            agg.allocation_count += 1; // ✅ INCREMENT ALLOCATION COUNT
          }
        }

        agg.total_area += activity.total_area || 0;
        agg.allocated_area += activity.allocated_area || 0;
      }
    }

    return map;
  }, [jobs]);

  const startOfMonth = currentMonth.startOf('month');
  const endOfMonth = currentMonth.endOf('month');
  const startOfCalendar = startOfMonth.startOf('week');
  const endOfCalendar = endOfMonth.endOf('week');

  const days: Dayjs[] = [];
  let d: Dayjs = startOfCalendar.clone();
  while (d.isBefore(endOfCalendar) || d.isSame(endOfCalendar, 'day')) {
    days.push(d);
    d = d.add(1, 'day');
  }

  const handlePrevMonth = () => setCurrentMonth((m) => m.subtract(1, 'month'));
  const handleNextMonth = () => setCurrentMonth((m) => m.add(1, 'month'));

  const isSameDay = (dateStr: string, day: Dayjs) =>
    dayjs(dateStr).isSame(day, 'day');

  const selectedAggregate = selectedDate ? dayMap[selectedDate] : null;

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'bg-green-50 text-green-700 border-green-200';
      case 'in_progress':
        return 'bg-orange-50 text-orange-700 border-orange-200';
      case 'fully_allocated':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'partially_allocated':
        return 'bg-yellow-50 text-yellow-700 border-yellow-200';
      default:
        return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="grid grid-cols-1 lg:grid-cols-12">
        {/* Calendar Grid */}
        <div className="lg:col-span-7 p-6 border-r border-gray-200">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              {currentMonth.format('MMMM YYYY')}
            </h2>
            <div className="flex items-center gap-2">
              <button
                onClick={handlePrevMonth}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ChevronLeft className="w-5 h-5 text-gray-600" />
              </button>
              <button
                onClick={() => setCurrentMonth(dayjs().startOf('month'))}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Today
              </button>
              <button
                onClick={handleNextMonth}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ChevronRight className="w-5 h-5 text-gray-600" />
              </button>
            </div>
          </div>

          {/* Days of Week */}
          <div className="grid grid-cols-7 mb-2">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
              <div
                key={day}
                className="text-center text-sm font-semibold text-gray-600 py-2"
              >
                {day}
              </div>
            ))}
          </div>

          {/* Calendar Grid */}
          <div className="grid grid-cols-7 gap-2">
            {days.map((dayObj) => {
              const dateStr = dayObj.format('YYYY-MM-DD');
              const agg = dayMap[dateStr];
              const isCurrentMonth = dayObj.isSame(currentMonth, 'month');
              const isToday = dayObj.isSame(dayjs(), 'day');
              const isSelected = selectedDate && isSameDay(selectedDate, dayObj);

              return (
                <button
                  key={dateStr}
                  onClick={() => setSelectedDate(agg ? dateStr : null)}
                  disabled={!agg}
                  className={`
                    relative min-h-[160px] p-3 rounded-lg border transition-all text-left
                    ${!isCurrentMonth ? 'bg-gray-50 opacity-50' : 'bg-white'}
                    ${isSelected ? 'border-blue-500 ring-2 ring-blue-200 shadow-md' : 'border-gray-200'}
                    ${agg && isCurrentMonth ? 'hover:border-blue-300 hover:shadow-sm cursor-pointer' : ''}
                    ${isToday && !isSelected ? 'border-blue-400' : ''}
                    ${!agg ? 'cursor-default' : ''}
                  `}
                >
                  {/* Date Number */}
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className={`
                        text-lg font-semibold
                        ${isToday ? 'bg-blue-600 text-white w-8 h-8 rounded-full flex items-center justify-center text-sm' : ''}
                        ${!isToday && isCurrentMonth ? 'text-gray-900' : 'text-gray-400'}
                      `}
                    >
                      {dayObj.date()}
                    </span>
                    {agg && (
                      <div className="flex flex-col items-end gap-0.5">
                        <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                          {agg.activities.length} act
                        </span>
                        {/* ✅ ALLOCATION COUNT BADGE */}
                        {agg.allocation_count > 0 && (
                          <span className="text-xs font-medium text-blue-600 bg-blue-100 px-2 py-0.5 rounded">
                            {agg.allocation_count} alloc
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Data */}
                  {agg ? (
                    <div className="space-y-2 text-xs">
                      {/* Job Counts */}
                      {(agg.ondemand_count > 0 || agg.tender_count > 0) && (
                        <div className="flex gap-2">
                          {agg.ondemand_count > 0 && (
                            <div className="flex-1 bg-blue-50 rounded px-2 py-1 text-center">
                              <div className="font-bold text-blue-700">{agg.ondemand_count}</div>
                              <div className="text-blue-600 text-[10px]">On-demand</div>
                            </div>
                          )}
                          {agg.tender_count > 0 && (
                            <div className="flex-1 bg-purple-50 rounded px-2 py-1 text-center">
                              <div className="font-bold text-purple-700">{agg.tender_count}</div>
                              <div className="text-purple-600 text-[10px]">Tender</div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Revenue
                      <div className="bg-green-50 rounded px-2 py-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-green-700 font-medium">Revenue</span>
                          <span className="font-bold text-green-800">
                            ₹{(agg.farmer_expected / 1000).toFixed(1)}K
                          </span>
                        </div>
                      </div>

                     
                      <div className="bg-red-50 rounded px-2 py-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-red-700 font-medium">Cost</span>
                          <span className="font-bold text-red-800">
                            ₹{(agg.mukkadam_cost / 1000).toFixed(1)}K
                          </span>
                        </div>
                      </div> */}

                      {/* ✅ AREA - SHOW BOTH ALLOCATED AND TOTAL */}
                      <div className="bg-gray-50 rounded px-2 py-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-gray-700 font-medium">Area</span>
                          <span className="font-bold text-gray-800">
                            {agg.allocated_area.toFixed(1)} / {agg.total_area.toFixed(1)}
                          </span>
                        </div>
                        <div className="mt-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-600 rounded-full"
                            style={{
                              width: `${Math.min((agg.allocated_area / agg.total_area) * 100, 100)}%`,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center text-xs text-gray-400 mt-8">
                      No activities
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Details Panel */}
        <div className="lg:col-span-5 p-6">
          {selectedAggregate ? (
            <div className="h-full">
              {/* Header */}
              <div className="mb-6">
                <h3 className="text-xl font-bold text-gray-900 mb-1">
                  {dayjs(selectedAggregate.date).format('DD MMMM YYYY')}
                </h3>
                <p className="text-sm text-gray-500">
                  {selectedAggregate.activities.length} activities • {selectedAggregate.jobs.length} jobs • {selectedAggregate.allocation_count} allocations
                </p>
              </div>

              {/* Summary Cards */}
              <div className="grid grid-cols-2 gap-3 mb-6">
                <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200">
                  <div className="flex items-center gap-2 mb-2">
                    <DollarSign className="w-4 h-4 text-green-700" />
                    <span className="text-xs font-semibold text-green-700">Revenue</span>
                  </div>
                  <div className="text-2xl font-bold text-green-900">
                    ₹{Math.round(selectedAggregate.farmer_expected).toLocaleString('en-IN')}
                  </div>
                </div>

                <div className="bg-gradient-to-br from-red-50 to-red-100 rounded-lg p-4 border border-red-200">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-4 h-4 text-red-700" />
                    <span className="text-xs font-semibold text-red-700">Cost</span>
                  </div>
                  <div className="text-2xl font-bold text-red-900">
                    ₹{Math.round(selectedAggregate.mukkadam_cost).toLocaleString('en-IN')}
                  </div>
                </div>

                <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200">
                  <div className="text-xs font-semibold text-blue-700 mb-2">
                    Total Work Area
                  </div>
                  <div className="text-2xl font-bold text-blue-900">
                    {selectedAggregate.total_area.toFixed(1)} ac
                  </div>
                  <div className="text-xs text-blue-600 mt-1">
                    {selectedAggregate.allocated_area.toFixed(1)} ac allocated
                  </div>
                  {/* ✅ PROGRESS BAR */}
                  <div className="mt-2 h-2 bg-blue-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-600 rounded-full transition-all"
                      style={{
                        width: `${Math.min((selectedAggregate.allocated_area / selectedAggregate.total_area) * 100, 100)}%`,
                      }}
                    />
                  </div>
                </div>

                <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
                  <div className="text-xs font-semibold text-purple-700 mb-2">
                    Profit Margin
                  </div>
                  <div className="text-2xl font-bold text-purple-900">
                    {selectedAggregate.farmer_expected > 0
                      ? (((selectedAggregate.farmer_expected - selectedAggregate.mukkadam_cost) / selectedAggregate.farmer_expected) * 100).toFixed(1)
                      : 0}%
                  </div>
                  <div className="text-xs text-purple-600 mt-1">
                    ₹{Math.round(selectedAggregate.farmer_expected - selectedAggregate.mukkadam_cost).toLocaleString('en-IN')} profit
                  </div>
                </div>
              </div>

              {/* Activities List */}
              <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
                {selectedAggregate.activities.map(({ job, activity }, index) => {
                  const farmerName = job.farmer?.farmer_name || job.farmer_id;
                  const bookingLabel = job.booking_type === 'TENDER' ? 'Tender' : 'On-demand';

                  const dayAllocations = activity.allocations.filter(
                    (a) => a.work_date === selectedAggregate.date
                  );
                  const allocCost = dayAllocations.reduce((sum, a) => sum + (a.total_cost || 0), 0);
                  const farmerExpected = activity.subtotal || activity.farmer_payments?.total_expected || activity.total_price || 0;

                  return (
                    <div
                      key={`${job.id}-${activity.activity_id}`}
                      className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors"
                    >
                      {/* Activity Header */}
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-bold text-gray-500">#{index + 1}</span>
                            <h4 className="text-sm font-bold text-gray-900">
                              {activity.activity_name}
                            </h4>
                            {/* ✅ SHOW ALLOCATION COUNT FOR THIS ACTIVITY */}
                            {dayAllocations.length > 0 && (
                              <span className="text-xs font-semibold text-blue-600 bg-blue-100 px-2 py-0.5 rounded">
                                {dayAllocations.length} alloc
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-gray-600 space-y-0.5">
                            <div>{activity.location}</div>
                            <div className="flex items-center gap-2">
                              <span>{farmerName}</span>
                              <span className="px-2 py-0.5 bg-white rounded text-xs font-semibold">
                                {bookingLabel}
                              </span>
                            </div>
                          </div>
                        </div>
                        <span className={`px-2 py-1 rounded text-xs font-semibold border ${getStatusColor(activity.allocation_status)}`}>
                          {activity.allocation_status.replace('_', ' ')}
                        </span>
                      </div>

                      {/* Financial Info */}
                      <div className="grid grid-cols-2 gap-2 mb-3">
                        <div className="bg-white rounded p-2 border border-green-200">
                          <div className="text-xs text-gray-600">Revenue</div>
                          <div className="text-sm font-bold text-green-700">
                            ₹{Math.round(farmerExpected).toLocaleString('en-IN')}
                          </div>
                        </div>
                        <div className="bg-white rounded p-2 border border-red-200">
                          <div className="text-xs text-gray-600">Cost</div>
                          <div className="text-sm font-bold text-red-700">
                            ₹{Math.round(allocCost).toLocaleString('en-IN')}
                          </div>
                        </div>
                      </div>

                      {/* ✅ AREA INFO - SHOW TOTAL AND ALLOCATED */}
                      <div className="bg-white rounded p-2 border border-gray-200 mb-3">
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="text-gray-600 font-semibold">Work Area</span>
                          <span className="font-bold text-gray-900">
                            {activity.allocated_area.toFixed(2)} / {activity.total_area.toFixed(2)} ac
                          </span>
                        </div>
                        <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-600 rounded-full transition-all"
                            style={{
                              width: `${Math.min((activity.allocated_area / activity.total_area) * 100, 100)}%`,
                            }}
                          />
                        </div>
                        <div className="flex items-center justify-between text-xs mt-1 text-gray-500">
                          <span>Rate: ₹{activity.rate_per_acre.toLocaleString('en-IN')}/ac</span>
                          <span>Remaining: {activity.remaining_area.toFixed(2)} ac</span>
                        </div>
                      </div>

                      {/* Allocations */}
                      {dayAllocations.length > 0 && (
                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-gray-700">
                            Allocations ({dayAllocations.length})
                          </div>
                          {dayAllocations.map((alloc) => (
                            <div key={alloc.allocation_id} className="bg-white rounded p-3 border border-gray-200 text-xs">
                              <div className="flex items-center justify-between mb-2">
                                <span className="font-bold text-gray-900">
                                  {alloc.mukkadam_name || 'Unknown team'}
                                </span>
                                <span className={`px-2 py-0.5 rounded font-semibold ${getStatusColor(alloc.status)}`}>
                                  {alloc.status}
                                </span>
                              </div>
                              <div className="grid grid-cols-2 gap-2 text-gray-600">
                                <div><span className="font-semibold">Workers:</span> {alloc.crew_size}</div>
                                <div><span className="font-semibold">Area:</span> {alloc.allocated_area} ac</div>
                                <div><span className="font-semibold">Labour:</span> ₹{Math.round(alloc.mukkadam_price).toLocaleString('en-IN')}</div>
                                <div><span className="font-semibold">Transport:</span> ₹{Math.round((alloc.transport_price || 0) + (alloc.own_transport_price || 0)).toLocaleString('en-IN')}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Farmer Payment */}
                      {activity.farmer_payments && (
                        <div className="mt-3 pt-3 border-t border-gray-200 text-xs">
                          <div className="flex items-center justify-between">
                            <div className="text-gray-600">
                              <span className="font-semibold">Farmer Paid:</span> ₹{Math.round(activity.farmer_payments.total_paid).toLocaleString('en-IN')} / ₹{Math.round(activity.farmer_payments.total_expected).toLocaleString('en-IN')}
                            </div>
                            <span className="px-2 py-1 bg-green-100 text-green-800 rounded font-bold">
                              {activity.farmer_payments.completion_percentage}%
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center py-20">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                <ChevronRight className="w-8 h-8 text-gray-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Select a Date
              </h3>
              <p className="text-sm text-gray-500 max-w-xs">
                Click on any date with activities to view detailed breakdown
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};