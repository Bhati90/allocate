# planning.py
import math
from collections import defaultdict
from datetime import timedelta

import requests
from django.core.cache import cache
from django.conf import settings

from .models import Cluster, JobActivity, Mukkadam, MukkadamActivityRate

DAILY_CAPACITY_URL = getattr(
    settings, "DAILY_CAPACITY_URL",
    # "http://localhost:8002/tender/api/mukkadams/daily_capacity_all/"
    "https://tender.bharatintelligence.ai/tender/api/mukkadams/daily_capacity_all/"
)
CACHE_TIMEOUT = 60 * 60 * 6   # 6 hours, busted by signals


# ─────────────────────────────────────────────────────────────────────────────
# Cache helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cache_key(cluster_id: int, start: str, end: str) -> str:
    return f"planning:v3:{cluster_id}:{start}:{end}"


def invalidate_planning_cache(cluster_id: int):
    registry = f"planning:keys:{cluster_id}"
    for k in (cache.get(registry) or set()):
        cache.delete(k)
    cache.delete(registry)


def _register_cache_key(cluster_id: int, key: str):
    registry = f"planning:keys:{cluster_id}"
    keys = cache.get(registry) or set()
    keys.add(key)
    cache.set(registry, keys, CACHE_TIMEOUT + 60)


# ─────────────────────────────────────────────────────────────────────────────
# Fetch capacity for ALL dates in range — ONE call per date (not per activity)
# Returns {date_str: {mukkadam_id: available_crew_size}}
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_capacity_range(cluster: Cluster, start_date, end_date) -> dict[str, dict[int, int]]:
    """
    Makes one HTTP call per date (unavoidable since API is date-based),
    but results are stored in a local dict so nothing else calls the API.
    """
    result: dict[str, dict[int, int]] = {}
    current = start_date
    while current <= end_date:
        key = current.isoformat()
        try:
            resp = requests.get(
                DAILY_CAPACITY_URL,
                params={"date": key, "cluster_id": cluster.id},
                timeout=5,
            )
            resp.raise_for_status()
            result[key] = {
                int(item["mukkadam_id"]): int(item["available_crew_size"])
                for item in resp.json()
                if int(item.get("available_crew_size", 0)) > 0
            }
        except Exception:
            result[key] = {}
        current += timedelta(days=1)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Build rate index: {activity_id: [{mukkadam_id, productivity, rate_per_acre}]}
# ONE DB query for the whole cluster — reused across all dates
# ─────────────────────────────────────────────────────────────────────────────

def _build_rate_index(cluster: Cluster) -> dict[int, list[dict]]:
    cluster_mukkadam_ids = set(
        Mukkadam.objects.filter(clusters=cluster)
        .values_list("mukkadam_id", flat=True)
    )
    rates = (
        MukkadamActivityRate.objects
        .filter(mukkadam__mukkadam_id__in=cluster_mukkadam_ids, is_active=True)
        .select_related("mukkadam", "activity")
    )
    index: dict[int, list[dict]] = defaultdict(list)
    for r in rates:
        index[r.activity_id].append({
            "mukkadam_id":   r.mukkadam.mukkadam_id,
            "mukkadam_name": r.mukkadam.mukkadam_name,
            "productivity":  float(r.productivity_per_worker or 0),
            "rate_per_acre": float(r.rate_per_acre or 0),
        })
    # Sort: highest productivity first (best team for each activity)
    for act_id in index:
        index[act_id].sort(key=lambda x: -x["productivity"])
    return dict(index)


# ─────────────────────────────────────────────────────────────────────────────
# Compute demand for one day purely from JobActivity bookings
# Returns (workers_needed_float, overflow_activities)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_day_demand(
    day_activities: list[dict],
    capacity_map: dict[int, int],   # {mukkadam_id: available_workers} for this date
    rate_index: dict[int, list[dict]],
) -> tuple[float, list[dict]]:
    """
    Greedy best-fit assignment based purely on booked area (remaining_area).
    No allocations involved at all.

    For each activity:
    - Find capable mukkadams (those with this activity in their rates AND available today)
    - Pick best fit: smallest surplus capacity that still covers the job
    - Tiebreak: cheapest rate
    - If nobody can cover fully → partial fit → leftover goes to overflow

    Returns total workers_needed and list of overflow activities.
    """
    avail = dict(capacity_map)   # mutable copy
    total_workers_needed = 0.0
    overflow = []

    # Largest area first — greedy fill
    for act in sorted(day_activities, key=lambda a: -a["remaining_area"]):
        act_id = act["activity_id"]
        area   = act["remaining_area"]
        if area <= 0:
            continue

        candidates = [
            c for c in rate_index.get(act_id, [])
            if c["productivity"] > 0 and avail.get(c["mukkadam_id"], 0) > 0
        ]

        if not candidates:
            # No capable mukkadam available today → full overflow
            # Estimate workers needed using best known productivity
            all_cands = rate_index.get(act_id, [])
            if all_cands:
                est = math.ceil(area / all_cands[0]["productivity"])
                total_workers_needed += est
            overflow.append({**act, "reason": "no_capacity_today"})
            continue

        best_full    = None
        best_partial = None

        for c in candidates:
            mid            = c["mukkadam_id"]
            prod           = c["productivity"]
            workers_needed = math.ceil(area / prod)
            workers_free   = avail[mid]
            max_area       = workers_free * prod
            surplus        = max_area - area

            if workers_free >= workers_needed:
                score = (surplus, c["rate_per_acre"])
                if best_full is None or score < best_full["score"]:
                    best_full = {
                        "score":          score,
                        "mukkadam_id":    mid,
                        "mukkadam_name":  c["mukkadam_name"],
                        "workers_needed": workers_needed,
                        "max_area":       max_area,
                    }
            else:
                if best_partial is None or max_area > best_partial["max_area"]:
                    best_partial = {
                        "mukkadam_id":    mid,
                        "mukkadam_name":  c["mukkadam_name"],
                        "workers_needed": workers_free,
                        "max_area":       max_area,
                    }

        chosen = best_full or best_partial

        if chosen:
            avail[chosen["mukkadam_id"]] = max(
                avail[chosen["mukkadam_id"]] - chosen["workers_needed"], 0
            )
            total_workers_needed += chosen["workers_needed"]
            area_leftover = round(max(area - chosen["max_area"], 0), 3)

            if best_full is None and area_leftover > 0.01:
                # Partial — leftover overflows
                overflow.append({
                    **act,
                    "remaining_area": area_leftover,
                    "reason": "partial_overflow",
                })
        else:
            total_workers_needed += math.ceil(
                area / rate_index[act_id][0]["productivity"]
            ) if rate_index.get(act_id) else 0
            overflow.append({**act, "reason": "no_capacity_today"})

    return total_workers_needed, overflow


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────
def build_planning_capacity_and_moves(
    cluster: Cluster,
    start_date,
    end_date,
    search_window_days: int = 7,
    force_recalc: bool = False,
) -> tuple[list, list]:

    cache_key = _cache_key(cluster.id, start_date.isoformat(), end_date.isoformat())
    if not force_recalc:
        cached = cache.get(cache_key)
        if cached:
            return cached["capacity_demand"], cached["move_suggestions"]

    rate_index     = _build_rate_index(cluster)
    capacity_range = _fetch_capacity_range(cluster, start_date, end_date)

    all_activities_qs = (
        JobActivity.objects
        .filter(
            job__clusters=cluster,
            scheduled_date__range=[start_date, end_date],
            remaining_area__gt=0,
            is_lost=False,
        )
        .select_related("job__farmer", "activity")
    )

    # Group by date — one DB query, grouped in Python
    acts_by_date: dict[str, list[dict]] = defaultdict(list)
    for ja in all_activities_qs:
        date_str = ja.scheduled_date.isoformat()
        acts_by_date[date_str].append({
            "job_id":            ja.job.job_id,
            "farmer_id":         ja.job.farmer.farmer_id,
            "farmer_name":       ja.job.farmer.farmer_name,
            "activity_id":       ja.activity.id,
            "activity_name":     ja.activity.name,
            "scheduled_date":    date_str,
            "remaining_area":    float(ja.remaining_area),
            "total_area":        float(ja.total_area),
            "is_manually_moved": ja.is_manually_moved,
            "is_strict":         getattr(ja, "is_strict", False),
        })

    capacity_demand  = []
    move_suggestions = []

    current = start_date
    while current <= end_date:
        date_str          = current.isoformat()
        cap_map           = capacity_range.get(date_str, {})
        day_acts          = acts_by_date.get(date_str, [])
        workers_available = sum(cap_map.values())

        workers_needed, overflow = _compute_day_demand(day_acts, cap_map, rate_index)

        shortage      = max(workers_needed - workers_available, 0)
        is_overbooked = shortage > 0

        capacity_demand.append({
            "date":             date_str,
            "capacity_workers": workers_available,
            "demand_workers":   round(workers_needed, 1),
            "shortage_workers": round(shortage, 1),
            "is_overbooked":    is_overbooked,
        })

        # ── Move suggestions: trigger on overbooked days (not just overflow)
        # Use ALL scheduled activities as candidates to move, not just overflow
        if is_overbooked and day_acts:
            move_suggestions.append({
                "overbooked_date":        date_str,
                "shortage_workers":       round(shortage, 1),
                "target_date":            None,   # filled in below
                "free_workers_on_target": 0,
                "can_fully_move":         False,
                "flexible_activities": [
                    {
                        "job_id":                a["job_id"],
                        "farmer_id":             a["farmer_id"],
                        "farmer_name":           a["farmer_name"],
                        "activity_id":           a["activity_id"],
                        "activity_name":         a["activity_name"],
                        "scheduled_date":        a["scheduled_date"],
                        "remaining_area":        a["remaining_area"],
                        "is_manually_moved":     a.get("is_manually_moved", False),
                        "reason":                "overbooked",
                        "suggested_target_date": None,
                    }
                    for a in day_acts
                    if not a.get("is_strict", False)   # skip strict activities
                ],
            })

        current += timedelta(days=1)

    # ── Auto-fill target_date from the freest available day ──────────────────
    # Build a lookup of free capacity per date (no extra API calls)
    free_days = sorted(
        [
            {
                "date":       cd["date"],
                "free":       cd["capacity_workers"] - cd["demand_workers"],
                "capacity":   cd["capacity_workers"],
            }
            for cd in capacity_demand
            if cd["capacity_workers"] > cd["demand_workers"]
        ],
        key=lambda x: -x["free"],   # most free first
    )

    for ms in move_suggestions:
        # Pick the nearest free day AFTER the overbooked date with enough capacity
        overbooked_dt = ms["overbooked_date"]
        best = None

        # First try: find a future free day with enough free workers
        for fd in free_days:
            if fd["date"] > overbooked_dt and fd["free"] >= ms["shortage_workers"]:
                best = fd
                break

        # Fallback: any future free day
        if not best:
            for fd in free_days:
                if fd["date"] > overbooked_dt:
                    best = fd
                    break

        # Last resort: any free day (even before)
        if not best and free_days:
            best = free_days[0]

        if best:
            ms["target_date"]            = best["date"]
            ms["free_workers_on_target"] = best["free"]
            ms["can_fully_move"]         = best["free"] >= ms["shortage_workers"]

    result = {"capacity_demand": capacity_demand, "move_suggestions": move_suggestions}
    cache.set(cache_key, result, CACHE_TIMEOUT)
    _register_cache_key(cluster.id, cache_key)

    return capacity_demand, move_suggestions