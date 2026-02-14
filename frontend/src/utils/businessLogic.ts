import {
  ActivityType,
  ACTIVITY_CONFIGS,
  Team,
  Farm,
  BookingActivity,
  TeamScore,
  Booking,
} from '../types/index';
import { distanceKm, calculateTravelCost } from './distance';
import { addDays, formatISO, parseISO } from './dateUtils';
// import { ActivityType } from '../types';

export function calculateActivityDuration(
  acres: number,
  activityType: ActivityType,
  workersAssigned: number,
  teamEfficiency: number
): number {
  const config = ACTIVITY_CONFIGS.find((c) => c.type === activityType)!;
  const baseProductivity = config.base_productivity;
  const workerRatio = workersAssigned / 10;
  const adjustedProductivity = baseProductivity * teamEfficiency * workerRatio;
  const durationDays = Math.ceil(acres / adjustedProductivity);
  return Math.max(durationDays, 1);
}

export function autoScheduleBookingActivities(
  booking: Booking,
  startDate: string,
  teamId: string,
  workersToAssign: number,
  team: Team
): BookingActivity[] {
  const activities: BookingActivity[] = [];
  let currentDate = parseISO(startDate);

  for (const config of ACTIVITY_CONFIGS) {
    const efficiency = team.efficiency_rating[config.type];
    const duration = calculateActivityDuration(
      booking.total_acres,
      config.type,
      workersToAssign,
      efficiency
    );

    const activity: BookingActivity = {
      id: `${booking.id}_ACT_${config.sequence_order}`,
      booking_id: booking.id,
      activity_type: config.type,
      sequence_order: config.sequence_order,
      scheduled_start_date: formatISO(currentDate),
      scheduled_end_date: formatISO(addDays(currentDate, duration - 1)),
      actual_start_date: null,
      actual_end_date: null,
      calculated_duration_days: duration,
      acres: booking.total_acres,
      assigned_team_id: teamId,
      assigned_workers: workersToAssign,
      status: 'not_started',
      completion_percentage: 0,
      delay_reason: null,
      team_cost: team.rate_per_activity[config.type] * booking.total_acres,
      travel_cost: 0,
      other_costs: 0,
      feedback: null,
    };

    activities.push(activity);
    currentDate = addDays(currentDate, duration + config.gap_days_after_previous);
  }

  return activities;
}

export function suggestBestTeam(
  farm: Farm,
  teams: Team[],
  hexagons: any[],
  activityType: ActivityType,
  acres: number
): TeamScore[] {
  const scores: TeamScore[] = [];

  for (const team of teams) {
    let score = 100;
    const reasons: string[] = [];

    const distance = distanceKm(
      team.base_location.lat,
      team.base_location.lng,
      farm.location.lat,
      farm.location.lng
    );

    if (distance <= 15) {
      score += 20;
      reasons.push('Within free travel radius');
    } else {
      score -= (distance - 15) * 2;
      reasons.push(`${distance.toFixed(1)} km away`);
    }

    const farmHex = hexagons.find((h) => h.id === farm.hexagon_id);
    if (farmHex && farmHex.assigned_teams.includes(team.id)) {
      score += 30;
      reasons.push('Owns this territory');
    }

    const efficiency = team.efficiency_rating[activityType];
    score += (efficiency - 1) * 20;
    if (efficiency > 1) {
      reasons.push(`${((efficiency - 1) * 100).toFixed(0)}% more efficient`);
    }

    const teamCost = team.rate_per_activity[activityType] * acres;
    const travelCost = calculateTravelCost(distance);

    scores.push({
      team_id: team.id,
      score: Math.max(score, 0),
      distance_km: distance,
      cost: teamCost + travelCost,
      availability: 100,
      reasons,
    });
  }

  return scores.sort((a, b) => b.score - a.score);
}
