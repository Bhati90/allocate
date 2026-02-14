// hooks/useMapData.ts
import { useMemo } from 'react';
import {
  generateNashikHexagons,
  findHexagonForPoint,
  extractLocationFromJob,
  extractLocationFromActivity,
  getVillageCoordinates,
  calculateAvailableDays,
  getFallbackLocation,
} from '../utils/hexagon';
import type { HexagonCluster, MukkadamPosition } from '../types/map';
import dayjs from 'dayjs';

const WORKERS_PER_ACRE = 10;
const APPROX_TOTAL_ACRES_PER_CLUSTER = 10000;

export function useMapData(jobs: any[], mukkadams: any[]) {
  const hexagonClusters = useMemo(() => {
    const baseHexagons = generateNashikHexagons();
    
    const clusters: HexagonCluster[] = baseHexagons.map((hex) => ({
      ...hex,
      villages: [],
      total_jobs: 0,
      total_activities: 0,
      total_allocations: 0,
      total_revenue: 0,
      total_cost: 0,
      profit: 0,
      profit_margin: 0,
      unique_farmers: 0,
      unique_mukkadams: 0,
      total_cultivable_acres: APPROX_TOTAL_ACRES_PER_CLUSTER,
      booked_acres: 0,
      allocated_acres: 0,
      pending_acres: 0,
      market_penetration: 0,
      available_workers: 0,
      needed_workers: 0,
      capacity_utilization: 0,
      pending_jobs: 0,
      upcoming_activities_week: 0,
      upcoming_activities_month: 0,
      demand_score: 0,
      status_counts: {
        pending: 0,
        partially_allocated: 0,
        fully_allocated: 0,
        in_progress: 0,
        completed: 0,
      },
      tender_count: 0,
      ondemand_count: 0,
      future_booked_acres: 0,
      future_needed_workers: 0,
      future_revenue: 0,
    }));
    
    const clusterMap = new Map(clusters.map((c) => [c.id, c]));
    const uniqueFarmersPerCluster = new Map<string, Set<string>>();
    const uniqueMukkadamsPerCluster = new Map<string, Set<number>>();
    
    // Initialize sets for tracking unique farmers/mukkadams
    for (const cluster of clusters) {
      uniqueFarmersPerCluster.set(cluster.id, new Set());
      uniqueMukkadamsPerCluster.set(cluster.id, new Set());
    }
    
    // ✅ Process each job with improved location extraction
    for (const job of jobs) {
      const locationData = extractLocationFromJob(job);
      
      const hexId = findHexagonForPoint(
        locationData.lat,
        locationData.lng,
        baseHexagons
      );
      
      if (!hexId) continue;
      
      const cluster = clusterMap.get(hexId);
      if (!cluster) continue;
      
      // Add village to cluster
      const villageName = job.farmer?.village || '';
      if (villageName && !cluster.villages.includes(villageName)) {
        cluster.villages.push(villageName);
      }
      
      // Count job
      cluster.total_jobs++;
      
      // Count by booking type
      if (job.booking_type === 'TENDER') {
        cluster.tender_count++;
      } else if (job.booking_type === 'ON_DEMAND') {
        cluster.ondemand_count++;
      }
      
      // Count by status
      const status = job.status?.toLowerCase() || 'pending';
      if (cluster.status_counts.hasOwnProperty(status)) {
        cluster.status_counts[status as keyof typeof cluster.status_counts]++;
      }
      
      // Track unique farmers
      if (job.farmer_id) {
        uniqueFarmersPerCluster.get(hexId)?.add(job.farmer_id);
      }
      
      // Process activities
      for (const activity of job.activities || []) {
        cluster.total_activities++;
        
        const totalArea = activity.total_area || 0;
        const allocatedArea = activity.allocated_area || 0;
        const remainingArea = activity.remaining_area || 0;
        
        cluster.booked_acres += totalArea;
        cluster.allocated_acres += allocatedArea;
        cluster.pending_acres += remainingArea;
        
        // Revenue
        const revenue = activity.subtotal || activity.total_price || 0;
        cluster.total_revenue += revenue;
        
        // Check if activity is in future
        const scheduledDate = dayjs(activity.scheduled_date);
        const today = dayjs();
        const weekFromNow = today.add(7, 'day');
        const monthFromNow = today.add(30, 'day');
        
        if (scheduledDate.isAfter(today)) {
          cluster.future_booked_acres += totalArea;
          cluster.future_needed_workers += Math.ceil(totalArea * WORKERS_PER_ACRE);
          cluster.future_revenue += revenue;
          
          if (scheduledDate.isBefore(weekFromNow)) {
            cluster.upcoming_activities_week++;
          }
          if (scheduledDate.isBefore(monthFromNow)) {
            cluster.upcoming_activities_month++;
          }
        }
        
        // Process allocations
        for (const alloc of activity.allocations || []) {
          cluster.total_allocations++;
          
          // Cost
          const cost = alloc.total_cost || 0;
          cluster.total_cost += cost;
          
          // Track unique mukkadams
          if (alloc.mukkadam_id) {
            uniqueMukkadamsPerCluster.get(hexId)?.add(alloc.mukkadam_id);
          }
        }
      }
      
      // Count pending jobs
      if (status === 'pending' || status === 'partially_allocated') {
        cluster.pending_jobs++;
      }
    }
    
    // ✅ Calculate mukkadam capacity per cluster with improved location handling
    for (const mukkadam of mukkadams) {
      let lat = mukkadam.current_latitude;
      let lng = mukkadam.current_longitude;
      
      // If no live location, try village
      if (!lat || !lng) {
        const villageCoords = getVillageCoordinates(mukkadam.village || '');
        if (villageCoords) {
          lat = villageCoords.lat;
          lng = villageCoords.lng;
        } else {
          // Use fallback
          const fallback = getFallbackLocation();
          lat = fallback.lat;
          lng = fallback.lng;
        }
      }
      
      const hexId = findHexagonForPoint(lat, lng, baseHexagons);
      if (!hexId) continue;
      
      const cluster = clusterMap.get(hexId);
      if (!cluster) continue;
      
      const crewSize = parseInt(mukkadam.crew_size) || 0;
      const availableDays = calculateAvailableDays(mukkadam);
      
      // Calculate effective workers based on availability
      const effectiveWorkers = crewSize * Math.min(availableDays / 30, 1);
      cluster.available_workers += effectiveWorkers;
    }
    
    // Calculate final metrics for each cluster
    for (const cluster of clusters) {
      // Set unique counts
      cluster.unique_farmers = uniqueFarmersPerCluster.get(cluster.id)?.size || 0;
      cluster.unique_mukkadams = uniqueMukkadamsPerCluster.get(cluster.id)?.size || 0;
      
      // Profit
      cluster.profit = cluster.total_revenue - cluster.total_cost;
      cluster.profit_margin =
        cluster.total_revenue > 0
          ? (cluster.profit / cluster.total_revenue) * 100
          : 0;
      
      // Market penetration
      cluster.market_penetration =
        (cluster.booked_acres / cluster.total_cultivable_acres) * 100;
      
      // Needed workers (for current pending work)
      cluster.needed_workers = Math.ceil(cluster.pending_acres * WORKERS_PER_ACRE);
      
      // Capacity utilization
      cluster.capacity_utilization =
        cluster.available_workers > 0
          ? Math.min((cluster.needed_workers / cluster.available_workers) * 100, 100)
          : cluster.needed_workers > 0 ? 100 : 0;
      
      // Demand score (0-100)
      const pendingScore = Math.min((cluster.pending_jobs / Math.max(cluster.total_jobs, 1)) * 50, 50);
      const areaScore = Math.min((cluster.pending_acres / Math.max(cluster.booked_acres, 1)) * 50, 50);
      cluster.demand_score = pendingScore + areaScore;
    }
    
    return clusters;
  }, [jobs, mukkadams]);
  
  const mukkadamPositions = useMemo((): MukkadamPosition[] => {
    const baseHexagons = generateNashikHexagons();
    
    return mukkadams.map((mukkadam) => {
      let latitude = mukkadam.current_latitude;
      let longitude = mukkadam.current_longitude;
      let isLive = true;
      
      // ✅ If no live location, use village or find from current allocation
      if (!latitude || !longitude) {
        isLive = false;
        
        // Try to find current allocation
        let foundAllocation = false;
        for (const job of jobs) {
          for (const activity of job.activities || []) {
            for (const alloc of activity.allocations || []) {
              if (alloc.mukkadam_id === mukkadam.id) {
                // Use activity location
                const locationData = extractLocationFromActivity(activity, job);
                latitude = locationData.lat;
                longitude = locationData.lng;
                foundAllocation = true;
                break;
              }
            }
            if (foundAllocation) break;
          }
          if (foundAllocation) break;
        }
        
        // Fallback to mukkadam's village
        if (!foundAllocation) {
          const coords = getVillageCoordinates(mukkadam.village || '');
          if (coords) {
            latitude = coords.lat;
            longitude = coords.lng;
          } else {
            // Ultimate fallback - operational area center
            const fallback = getFallbackLocation();
            latitude = fallback.lat;
            longitude = fallback.lng;
          }
        }
      }
      
      const clusterId = findHexagonForPoint(latitude, longitude, baseHexagons);
      
      // Find current allocation details
      let currentAllocation = undefined;
      for (const job of jobs) {
        for (const activity of job.activities || []) {
          for (const alloc of activity.allocations || []) {
            if (alloc.mukkadam_id === mukkadam.id && alloc.status !== 'completed') {
              currentAllocation = {
                job_id: job.id,
                activity_name: activity.activity_name,
                location: activity.location,
              };
              break;
            }
          }
          if (currentAllocation) break;
        }
        if (currentAllocation) break;
      }
      
      const availableDays = calculateAvailableDays(mukkadam);
      
      return {
        id: mukkadam.id,
        name: mukkadam.mukkadam_name,
        latitude,
        longitude,
        crew_size: parseInt(mukkadam.crew_size) || 0,
        cluster_id: clusterId,
        is_live_location: isLive,
        current_allocation: currentAllocation,
        availability: {
          is_available: availableDays > 0,
          available_days: availableDays,
          start_date: mukkadam.start_date || null,
          end_date: mukkadam.end_date || null,
        },
      };
    });
  }, [mukkadams, jobs]);
  
  return { hexagonClusters, mukkadamPositions };
}