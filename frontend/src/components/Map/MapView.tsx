// components/MapView/MapView.tsx - Add filters
import React, { useState, useEffect, useMemo } from 'react';
import { MapPin, Users, TrendingUp, DollarSign, Loader2,X } from 'lucide-react';
import { useMapData } from '../../hooks/useMapData';
import { HexagonDetails } from './HexagonDetails';
import { OptimizationPanel } from './OptimizationPanel';
// import { LeafletHexagonMap } from './HexaMap';
// import { MapFilters } from './MapFilters';
import dayjs from 'dayjs';
import { MapFilters } from './MapFilter';
import { LeafletHexagonMap } from './HexaMapView';

type ViewMode = 'penetration' | 'capacity' | 'demand';

type FilterState = {
  search: string;
  bookingType: 'ALL' | 'TENDER' | 'ON_DEMAND';
  status: string;
  village: string;
  mukkadamName: string;
  dateFrom: string;
  dateTo: string;
  minRevenue: string;
  maxRevenue: string;
  minPenetration: string;
  maxPenetration: string;
};

export function MapView() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [mukkadams, setMukkadams] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [selectedHexId, setSelectedHexId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('penetration');
  const [showOptimizations, setShowOptimizations] = useState(true);
  
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    bookingType: 'ALL',
    status: '',
    village: '',
    mukkadamName: '',
    dateFrom: '',
    dateTo: '',
    minRevenue: '',
    maxRevenue: '',
    minPenetration: '',
    maxPenetration: '',
  });

  // Fetch data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [jobsRes, mukkadamsRes] = await Promise.all([
          fetch('http://localhost:8001/ap/jobs/'),
          fetch('http://localhost:8000/api/mukkadam/minimal_list/'),
        ]);

        if (!jobsRes.ok || !mukkadamsRes.ok) {
          throw new Error('Failed to fetch data');
        }

        const jobsData = await jobsRes.json();
        const mukkadamsData = await mukkadamsRes.json();

        setJobs(jobsData);
        setMukkadams(mukkadamsData);
      } catch (e: any) {
        setError(e.message || 'Failed to load map data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Apply filters to jobs
  const filteredJobs = useMemo(() => {
    let filtered = [...jobs];

    // Booking type filter
    if (filters.bookingType !== 'ALL') {
      filtered = filtered.filter(
        (job) => job.booking_type?.toUpperCase() === filters.bookingType
      );
    }

    // Status filter
    if (filters.status) {
      filtered = filtered.filter(
        (job) => job.status?.toLowerCase() === filters.status.toLowerCase()
      );
    }

    // Village filter
    if (filters.village) {
      filtered = filtered.filter((job) =>
        job.farmer?.village?.toLowerCase().includes(filters.village.toLowerCase()) ||
        job.activities?.some((act: any) =>
          act.location?.toLowerCase().includes(filters.village.toLowerCase())
        )
      );
    }

    // Mukkadam filter
    if (filters.mukkadamName) {
      filtered = filtered.filter((job) =>
        job.activities?.some((activity: any) =>
          activity.allocations?.some((alloc: any) =>
            alloc.mukkadam_name?.toLowerCase().includes(filters.mukkadamName.toLowerCase())
          )
        )
      );
    }

    // Date range filter
    if (filters.dateFrom) {
      filtered = filtered.filter((job) =>
        job.activities?.some((activity: any) =>
          dayjs(activity.scheduled_date).isSameOrAfter(dayjs(filters.dateFrom), 'day')
        )
      );
    }

    if (filters.dateTo) {
      filtered = filtered.filter((job) =>
        job.activities?.some((activity: any) =>
          dayjs(activity.scheduled_date).isSameOrBefore(dayjs(filters.dateTo), 'day')
        )
      );
    }

    // Search filter (cluster ID, job ID, farmer name)
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter((job) =>
        job.id?.toLowerCase().includes(searchLower) ||
        job.work_id?.toLowerCase().includes(searchLower) ||
        job.farmer?.farmer_name?.toLowerCase().includes(searchLower) ||
        job.farmer_id?.toLowerCase().includes(searchLower)
      );
    }

    return filtered;
  }, [jobs, filters]);

  const { hexagonClusters, mukkadamPositions } = useMapData(filteredJobs, mukkadams);

  // Apply cluster-level filters
  const filteredHexagons = useMemo(() => {
    let filtered = [...hexagonClusters];

    // Revenue filter
    if (filters.minRevenue) {
      const min = parseFloat(filters.minRevenue);
      filtered = filtered.filter((hex) => hex.total_revenue >= min);
    }

    if (filters.maxRevenue) {
      const max = parseFloat(filters.maxRevenue);
      filtered = filtered.filter((hex) => hex.total_revenue <= max);
    }

    // Penetration filter
    if (filters.minPenetration) {
      const min = parseFloat(filters.minPenetration);
      filtered = filtered.filter((hex) => hex.market_penetration >= min);
    }

    if (filters.maxPenetration) {
      const max = parseFloat(filters.maxPenetration);
      filtered = filtered.filter((hex) => hex.market_penetration <= max);
    }

    return filtered;
  }, [hexagonClusters, filters]);

  // Get unique villages and mukkadam names for filter dropdowns
  const uniqueVillages = useMemo(() => {
    const villages = new Set<string>();
    jobs.forEach((job) => {
      if (job.farmer?.village) villages.add(job.farmer.village);
      job.activities?.forEach((act: any) => {
        if (act.location) villages.add(act.location);
      });
    });
    return Array.from(villages);
  }, [jobs]);

  const uniqueMukkadamNames = useMemo(() => {
    const names = new Set<string>();
    mukkadams.forEach((m) => {
      if (m.mukkadam_name) names.add(m.mukkadam_name);
    });
    return Array.from(names);
  }, [mukkadams]);

  const selectedHexagon = filteredHexagons.find((h) => h.id === selectedHexId);

  // Calculate district-wide metrics
  const totalAcres = filteredHexagons.reduce((sum, h) => sum + h.total_cultivable_acres, 0);
  const bookedAcres = filteredHexagons.reduce((sum, h) => sum + h.booked_acres, 0);
  const totalRevenue = filteredHexagons.reduce((sum, h) => sum + h.total_revenue, 0);
  const totalCost = filteredHexagons.reduce((sum, h) => sum + h.total_cost, 0);
  const totalProfit = totalRevenue - totalCost;
  const activeHexagons = filteredHexagons.filter((h) => h.total_jobs > 0).length;
  const avgPenetration = totalAcres > 0 ? ((bookedAcres / totalAcres) * 100).toFixed(1) : '0';
  const totalWorkers = mukkadamPositions.reduce((sum, m) => sum + m.crew_size, 0);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-lg text-gray-700 font-medium">Loading map data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl shadow-2xl p-10 max-w-md">
          <div className="text-red-600 text-center">
            <svg className="w-16 h-16 mx-auto mb-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-2xl font-bold mb-3">Error Loading Map</h3>
            <p className="text-gray-600">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-gray-100 p-8">
      <div className="max-w-[1800px] mx-auto space-y-6">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                Territory Management
              </h1>
              <p className="text-gray-600 mt-2 text-lg">Nashik District - Hexagonal Cluster Analysis</p>
            </div>

            <div className="flex gap-3">
              <select
                className="px-5 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-medium"
                value={viewMode}
                onChange={(e) => setViewMode(e.target.value as ViewMode)}
              >
                <option value="penetration">Market Penetration</option>
                <option value="capacity">Team Capacity</option>
                <option value="demand">Demand Score</option>
              </select>

              <button
                className={`px-6 py-3 rounded-xl font-semibold transition-all ${
                  showOptimizations
                    ? 'bg-blue-600 text-white shadow-lg'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
                onClick={() => setShowOptimizations(!showOptimizations)}
              >
                {showOptimizations ? '✓ ' : ''}Show Optimizations
              </button>
            </div>
          </div>

          {/* District Summary Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-5 rounded-xl border-2 border-blue-200">
              <div className="flex items-center gap-2 text-blue-700 mb-2">
                <MapPin className="w-5 h-5" />
                <span className="text-sm font-semibold">Hexagons</span>
              </div>
              <div className="text-3xl font-bold text-blue-900">{filteredHexagons.length}</div>
              <div className="text-xs text-blue-600 mt-1">{activeHexagons} active</div>
            </div>

            <div className="bg-gradient-to-br from-emerald-50 to-teal-50 p-5 rounded-xl border-2 border-emerald-200">
              <div className="flex items-center gap-2 text-emerald-700 mb-2">
                <Users className="w-5 h-5" />
                <span className="text-sm font-semibold">Teams</span>
              </div>
              <div className="text-3xl font-bold text-emerald-900">{mukkadamPositions.length}</div>
              <div className="text-xs text-emerald-600 mt-1">{totalWorkers} workers</div>
            </div>

            <div className="bg-gradient-to-br from-amber-50 to-orange-50 p-5 rounded-xl border-2 border-amber-200">
              <div className="flex items-center gap-2 text-amber-700 mb-2">
                <TrendingUp className="w-5 h-5" />
                <span className="text-sm font-semibold">Penetration</span>
              </div>
              <div className="text-3xl font-bold text-amber-900">{avgPenetration}%</div>
              <div className="text-xs text-amber-600 mt-1">District avg</div>
            </div>

            {/* <div className="bg-gradient-to-br from-purple-50 to-pink-50 p-5 rounded-xl border-2 border-purple-200">
              <div className="flex items-center gap-2 text-purple-700 mb-2">
                <DollarSign className="w-5 h-5" />
                <span className="text-sm font-semibold">Revenue</span>
              </div>
              <div className="text-3xl font-bold text-purple-900">
                ₹{(totalRevenue / 100000).toFixed(1)}L
              </div>
              <div className="text-xs text-purple-600 mt-1">Total booked</div>
            </div> */}

            {/* <div className="bg-gradient-to-br from-rose-50 to-red-50 p-5 rounded-xl border-2 border-rose-200">
              <div className="flex items-center gap-2 text-rose-700 mb-2">
                <TrendingUp className="w-5 h-5" />
                <span className="text-sm font-semibold">Profit</span>
              </div>
              <div className="text-3xl font-bold text-rose-900">
                ₹{(totalProfit / 100000).toFixed(1)}L
              </div>
              <div className="text-xs text-rose-600 mt-1">
                {totalRevenue > 0 ? ((totalProfit / totalRevenue) * 100).toFixed(1) : 0}% margin
              </div>
            </div> */}

            <div className="bg-gradient-to-br from-cyan-50 to-blue-50 p-5 rounded-xl border-2 border-cyan-200">
              <div className="flex items-center gap-2 text-cyan-700 mb-2">
                <MapPin className="w-5 h-5" />
                <span className="text-sm font-semibold">Area</span>
              </div>
              <div className="text-3xl font-bold text-cyan-900">{bookedAcres.toFixed(0)}</div>
              <div className="text-xs text-cyan-600 mt-1">of {totalAcres.toFixed(0)} acres</div>
            </div>
          </div>
        </div>

        {/* Filters */}
         {/* Filters */}
        <MapFilters
          filters={filters}
          onChange={setFilters}
          villages={uniqueVillages}
          mukkadamNames={uniqueMukkadamNames}
        />
                {/* ✅ Main Content - Map takes full width, optimizations below */}
        <div className="space-y-6">
          {/* Map - Full Width */}
          <LeafletHexagonMap
            hexagons={filteredHexagons}
            mukkadams={mukkadamPositions}
            viewMode={viewMode}
            selectedHexId={selectedHexId}
            onSelectHex={setSelectedHexId}
          />

          
        </div>

        {/* ✅ Selected Cluster Details - Shows at top when cluster selected */}
        {selectedHexagon && (
          <div className="bg-white rounded-2xl shadow-xl border-2 border-blue-500 p-6 animate-fadeIn">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                Selected Cluster: {selectedHexagon.id}
              </h2>
              <button
                onClick={() => setSelectedHexId(null)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
                Close
              </button>
            </div>
            <HexagonDetails hexagon={selectedHexagon} jobs={filteredJobs} mukkadams={mukkadamPositions} />
          </div>
        )}

        {/* Optimizations - Full Width Below Map */}
          {showOptimizations && (
            <OptimizationPanel
              hexagons={filteredHexagons}
              mukkadams={mukkadamPositions}
              onSelectHex={setSelectedHexId}
            />
          )}


      </div>
    </div>
  );
}