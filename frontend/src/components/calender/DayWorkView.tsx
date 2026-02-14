import React, { useMemo } from 'react';
import { useApp } from '../../context/AppContext';
import { formatDisplayDate } from '../../utils/dateUtils';
import { ACTIVITY_CONFIGS } from '../../types/index';

type Props = {
  date: string; // 'YYYY-MM-DD'
};

export const DayWorkView: React.FC<Props> = ({ date }) => {
  const { bookings, farms, teams } = useApp();

  // All activities that touch this date (scheduled_start <= date <= scheduled_end)
  const activitiesToday = useMemo(() => {
    return bookings.flatMap((booking) => {
      const farm = farms.find((f) => f.id === booking.farm_id);
      if (!farm) return [];

      return booking.activities
        .filter((act) => act.scheduled_start_date && act.scheduled_end_date)
        .filter(
          (act) =>
            act.scheduled_start_date! <= date &&
            act.scheduled_end_date! >= date
        )
        .map((act) => ({
          booking,
          farm,
          act,
          team: act.assigned_team_id
            ? teams.find((t) => t.id === act.assigned_team_id) || null
            : null,
        }));
    });
  }, [bookings, farms, teams, date]);

  const farmerSide = activitiesToday; // same list, just grouped differently
  const teamSideByTeam = useMemo(() => {
    const map: Record<string, typeof activitiesToday> = {};
    for (const item of activitiesToday) {
      const key = item.team?.id || 'UNASSIGNED';
      if (!map[key]) map[key] = [];
      map[key].push(item);
    }
    return map;
  }, [activitiesToday]);

  // Money summary
  const summary = useMemo(() => {
    let revenueToday = 0;
    let costToday = 0;

    for (const { booking, act } of activitiesToday) {
      // Simple approximation: spread cost & revenue equally per day
      const totalDays = act.calculated_duration_days || 1;
      const dailyTeamCost = act.team_cost / totalDays;
      const dailyTravelCost = act.travel_cost / totalDays;
      const dailyOtherCost = act.other_costs / totalDays;

      // allocate booking revenue equally across its total days
      const totalBookingDays = booking.activities.reduce(
        (sum, a) => sum + (a.calculated_duration_days || 0),
        0
      );
      const dailyRevenue =
        totalBookingDays > 0 ? booking.total_revenue / totalBookingDays : 0;

      revenueToday += dailyRevenue;
      costToday += dailyTeamCost + dailyTravelCost + dailyOtherCost;
    }

    return {
      revenueToday: Math.round(revenueToday),
      costToday: Math.round(costToday),
      profitToday: Math.round(revenueToday - costToday),
    };
  }, [activitiesToday]);

  const getActivityLabel = (type: string) =>
    ACTIVITY_CONFIGS.find((c) => c.type === type)?.display_name || type;

  return (
    <div className="max-w-[1400px] mx-auto space-y-6">
      {/* Header + summary */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold">
              Work for {formatDisplayDate(date)}
            </h2>
            <p className="text-sm text-gray-500">
              All farmer commitments and team allocations on this day.
            </p>
          </div>

          <input
            type="date"
            value={date}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
            readOnly
          />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
            <div className="text-xs text-emerald-700 font-medium mb-1">
              Farmer Revenue (Expected)
            </div>
            <div className="text-2xl font-bold text-emerald-900">
              ₹{summary.revenueToday.toLocaleString('en-IN')}
            </div>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <div className="text-xs text-amber-700 font-medium mb-1">
              Costs to Teams (Wages + Travel)
            </div>
            <div className="text-2xl font-bold text-amber-900">
              ₹{summary.costToday.toLocaleString('en-IN')}
            </div>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="text-xs text-blue-700 font-medium mb-1">
              Daily Profit (Approx)
            </div>
            <div className="text-2xl font-bold text-blue-900">
              ₹{summary.profitToday.toLocaleString('en-IN')}
            </div>
          </div>
        </div>
      </div>

      {/* Columns: Farmer side vs Team side */}
      <div className="grid grid-cols-2 gap-6">
        {/* Farmer side */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold text-gray-900">
              From Farmer Side
            </h3>
            <span className="text-xs text-gray-500">
              {farmerSide.length} activity slots
            </span>
          </div>

          <div className="space-y-3 max-h-[550px] overflow-y-auto pr-2">
            {farmerSide.length === 0 && (
              <p className="text-sm text-gray-500">
                No activities scheduled for farmers on this day.
              </p>
            )}

            {farmerSide.map(({ booking, farm, act }) => (
              <div
                key={act.id}
                className="border border-gray-200 rounded-lg p-3 hover:border-blue-300 hover:shadow-sm transition-all bg-white"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="font-semibold text-gray-900 text-sm">
                    {farm.farmer_name} – {farm.location.village}
                  </div>
                  <span className="text-xs rounded-full px-2 py-0.5 bg-gray-100 text-gray-600">
                    {booking.id}
                  </span>
                </div>

                <div className="text-xs text-gray-500 mb-1">
                  {farm.crop_type} • {farm.total_acres} acres
                </div>

                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-gray-800">
                    {getActivityLabel(act.activity_type)} • {act.acres} ac
                  </span>
                  <span className="text-gray-500">
                    {act.scheduled_start_date} → {act.scheduled_end_date}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs mt-1">
                  <span className="text-gray-500">
                    Status:{' '}
                    <span className="font-semibold text-gray-800">
                      {act.status}
                    </span>
                  </span>
                  <span className="text-gray-500">
                    Progress:{' '}
                    <span className="font-semibold">
                      {act.completion_percentage}%
                    </span>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Team / Mukkadam side */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold text-gray-900">
              Work Given to Mukkadam / Teams
            </h3>
            <span className="text-xs text-gray-500">
              {Object.keys(teamSideByTeam).length} team buckets
            </span>
          </div>

          <div className="space-y-4 max-h-[550px] overflow-y-auto pr-2">
            {Object.entries(teamSideByTeam).map(([teamId, items]) => {
              const team =
                teamId === 'UNASSIGNED'
                  ? null
                  : teams.find((t) => t.id === teamId);
              const totalAcres = items.reduce((sum, i) => sum + i.act.acres, 0);
              const totalWorkers = items.reduce(
                (sum, i) => sum + i.act.assigned_workers,
                0
              );

              const dailyTeamCost = items.reduce((sum, i) => {
                const d = i.act.calculated_duration_days || 1;
                return sum + i.act.team_cost / d + i.act.travel_cost / d + i.act.other_costs / d;
              }, 0);

              return (
                <div
                  key={teamId}
                  className="border border-gray-200 rounded-lg p-3 bg-white"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="font-semibold text-gray-900 text-sm">
                        {team
                          ? `${team.name} (${team.total_workers} workers)`
                          : 'UNASSIGNED WORK'}
                      </div>
                      {team && (
                        <div className="text-xs text-gray-500">
                          {team.mukkadam_name} • {team.base_location.village}
                        </div>
                      )}
                    </div>
                    <div className="text-right text-xs">
                      <div className="text-gray-500">Total acres today</div>
                      <div className="font-semibold text-gray-900">
                        {totalAcres.toFixed(1)} ac
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs mb-2">
                    <span className="text-gray-500">
                      Workers allocated:{' '}
                      <span className="font-semibold text-gray-800">
                        {totalWorkers}
                      </span>
                    </span>
                    <span className="text-gray-500">
                      Cost today:{' '}
                      <span className="font-semibold text-amber-700">
                        ₹{Math.round(dailyTeamCost).toLocaleString('en-IN')}
                      </span>
                    </span>
                  </div>

                  <div className="space-y-1 border-t pt-2 mt-2">
                    {items.map(({ farm, act }) => (
                      <div
                        key={act.id}
                        className="flex items-center justify-between text-xs"
                      >
                        <div className="flex flex-col">
                          <span className="font-medium text-gray-800">
                            {getActivityLabel(act.activity_type)} –{' '}
                            {farm.location.village}
                          </span>
                          <span className="text-gray-500">
                            {act.acres} ac • {act.assigned_workers} workers
                          </span>
                        </div>
                        <div className="text-right text-gray-500">
                          <div>
                            {act.scheduled_start_date} → {act.scheduled_end_date}
                          </div>
                          <div>
                            {act.status === 'delayed' && (
                              <span className="text-red-600 font-semibold">
                                DELAYED
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}

            {activitiesToday.length === 0 && (
              <p className="text-sm text-gray-500">
                No team work assigned on this day.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
