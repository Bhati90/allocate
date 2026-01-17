import moment from 'moment';

export interface ScoredMukkadam {
  id: number;
  mukkadam_name: string;
  village: string;
  crew_size: string;
  mobile_numbers: string;
  recommendation_score: number;
  recommendation_reasons: string[];
  is_blocked: boolean; // If already booked on that day
}

export const getRecommendedMukkadams = (
  richMukkadamList: any[], // The list from scorecard-summary API
  target: {
    date: string;
    farmerId: string;
    activityName: string;
    location: { district: string; taluka: string };
  }
): ScoredMukkadam[] => {
  if (!target.date || !richMukkadamList.length) return [];

  return richMukkadamList.map((mukkadam) => {
    let score = 0;
    let reasons: string[] = [];
    let isBlocked = false;

    // --- 1. AVAILABILITY CHECK (Hard Filter) ---
    // Check if booked on this specific date
    const isBookedToday = mukkadam.job_summary?.some((job: any) => 
        job.work_date === target.date && 
        ['allocated', 'in_progress'].includes(job.status)
    );

    if (isBookedToday) {
        score = -100; 
        isBlocked = true;
        reasons.push("⛔ Booked");
    } else {
        // Base score for being available
        score += 50;
    }

    if (isBlocked) {
        return { ...mukkadam, recommendation_score: score, recommendation_reasons: reasons, is_blocked: true };
    }

    // --- 2. LOGISTICS (Nearby +/- 3 Days) ---
    const nearStartDate = moment(target.date).subtract(3, 'days');
    const nearEndDate = moment(target.date).add(3, 'days');

    const logisticsMatch = mukkadam.job_summary?.some((job: any) => {
        const jobDate = moment(job.work_date);
        const isNearDate = jobDate.isBetween(nearStartDate, nearEndDate, 'day', '[]');
        
        // Check location match (String check in farmer location)
        const locString = (job.farmer?.location || "").toLowerCase();
        const targetTaluka = (target.location.taluka || "").toLowerCase();
        
        return isNearDate && targetTaluka && locString.includes(targetTaluka);
    });

    if (logisticsMatch) {
        score += 40;
        reasons.push("🚚 Nearby");
    }

    // --- 3. FARMER RELATIONSHIP ---
    const workedWithFarmer = mukkadam.job_summary?.some((job: any) => 
        String(job.farmer?.farmer_id) === String(target.farmerId)
    );

    if (workedWithFarmer) {
        score += 30;
        reasons.push("🤝 Known to Farmer");
    }

    // --- 4. ACTIVITY EXPERTISE ---
    const activityCount = mukkadam.job_summary?.filter((job: any) => 
        job.activity?.activity_name === target.activityName
    ).length || 0;

    if (activityCount > 5) {
        score += 20;
        reasons.push(`⭐ Expert (${activityCount} jobs)`);
    }

    // --- 5. NEWCOMER / LOCAL BOOST ---
    const isNew = moment().diff(moment(mukkadam.created_at), 'days') < 90;
    const isLocal = (mukkadam.taluka || "").toLowerCase() === (target.location.taluka || "").toLowerCase();

    if (isNew && isLocal) {
        score += 25;
        reasons.push("🌱 New & Local");
    }

    return {
      ...mukkadam,
      recommendation_score: score,
      recommendation_reasons: reasons,
      is_blocked: isBlocked
    };
  }).sort((a, b) => b.recommendation_score - a.recommendation_score);
};