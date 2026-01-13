// import React, { useState, useEffect } from 'react';
// import axios from 'axios';
// import { 
//   Users, Calendar, TrendingUp, AlertCircle, DollarSign,
//   MapPin, Filter, Search, Activity, Award, Target,
//   CheckCircle, Clock, Zap, BarChart3, Map as MapIcon
// } from 'lucide-react';
// import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet';
// import 'leaflet/dist/leaflet.css';

// const API_BASE = import.meta.env.VITE_API_BASE_URL_SUPPLY;

// const ActiveMukkadamsDashboard = () => {
//   const [data, setData] = useState(null);
//   const [loading, setLoading] = useState(true);
//   const [showFilters, setShowFilters] = useState(false);
  
//   // Filter states
//   const [filters, setFilters] = useState({
//     has_availability: '',
//     has_allocations: '',
//     village: '',
//     min_crew: '',
//     registered_by: ''
//   });

//   // Computed metrics
//   const [metrics, setMetrics] = useState({
//     activeTeams: 0,
//     availableManDays: 0,
//     avgUtilization: 0,
//     idleTeams: 0,
//     avgEarningsPerPersonPerDay: 0,
//     teamsRegistered: 0,
//     teamsActivated: 0,
//     activationRate: 0,
//     avgDaysToFirstJob: 0
//   });

//   const [utilizationBuckets, setUtilizationBuckets] = useState({
//     '0-25': [],
//     '25-50': [],
//     '50-75': [],
//     '75-90': [],
//     '90+': []
//   });

//   const [topPerformers, setTopPerformers] = useState({
//     highest: null,
//     lowest: null
//   });

//   useEffect(() => {
//     fetchData();
//   }, []);

//   const fetchData = async () => {
//     try {
//       setLoading(true);
//       const token = localStorage.getItem('auth_token');
      
//       const params = {};
//       Object.keys(filters).forEach(key => {
//         if (filters[key]) params[key] = filters[key];
//       });

//       const response = await axios.get(`${API_BASE}/api/mukkadam/active_mukkadams/`, {
//         params,
//         headers: { Authorization: `Token ${token}` }
//       });
      
//       setData(response.data);
//       calculateMetrics(response.data);
//       categorizeByUtilization(response.data);
//       findTopPerformers(response.data);
      
//     } catch (err) {
//       console.error("Error fetching active mukkadams:", err);
//     } finally {
//       setLoading(false);
//     }
//   };

//   const calculateMetrics = (responseData) => {
//     if (!responseData || !responseData.data) return;

//     const mukkadams = responseData.data;
    
//     // Active Teams
//     const activeTeams = mukkadams.length;
    
//     // Available Man Days (sum of future availability slots * crew size)
//     const availableManDays = mukkadams.reduce((sum, m) => {
//       const futureSlots = m.availability.future_slots || 0;
//       return sum + (futureSlots * m.crew_size);
//     }, 0);
    
//     // Average Utilization
//     const totalUtilization = mukkadams.reduce((sum, m) => {
//       return sum + (m.performance?.completion_rate || 0);
//     }, 0);
//     const avgUtilization = activeTeams > 0 ? totalUtilization / activeTeams : 0;
    
//     // Idle Teams (< 25% utilization)
//     const idleTeams = mukkadams.filter(m => 
//       (m.performance?.completion_rate || 0) < 25
//     ).length;
    
//     // Avg Earnings Per Person Per Day
//     const totalEarnings = mukkadams.reduce((sum, m) => 
//       sum + m.financial_summary.total_earnings_paid, 0
//     );
//     const totalWorkDays = mukkadams.reduce((sum, m) => 
//       sum + m.financial_summary.total_area_worked, 0
//     );
//     const totalPersonDays = mukkadams.reduce((sum, m) => 
//       sum + (m.allocations.completed * m.crew_size), 0
//     );
//     const avgEarningsPerPersonPerDay = totalPersonDays > 0 
//       ? totalEarnings / totalPersonDays 
//       : 0;
    
//     // Teams Registered (total in system)
//     const teamsRegistered = responseData.summary.total_active_mukkadams;
    
//     // Teams Activated (have allocations)
//     const teamsActivated = mukkadams.filter(m => 
//       m.activity_status.has_allocations
//     ).length;
    
//     // Activation Rate
//     const activationRate = teamsRegistered > 0 
//       ? (teamsActivated / teamsRegistered * 100) 
//       : 0;
    
//     // Avg Days to First Job (calculate from registration to first allocation)
//     const daysToFirstJob = mukkadams
//       .filter(m => m.allocations.total_allocations > 0)
//       .map(m => {
//         const registeredDate = new Date(m.registration_info.registered_at);
//         const firstJob = m.allocations.all_allocations[m.allocations.all_allocations.length - 1];
//         if (firstJob && firstJob.work_date) {
//           const firstJobDate = new Date(firstJob.work_date);
//           return (firstJobDate - registeredDate) / (1000 * 60 * 60 * 24);
//         }
//         return 0;
//       })
//       .filter(days => days > 0);
    
//     const avgDaysToFirstJob = daysToFirstJob.length > 0
//       ? daysToFirstJob.reduce((a, b) => a + b, 0) / daysToFirstJob.length
//       : 0;

//     setMetrics({
//       activeTeams,
//       availableManDays,
//       avgUtilization: avgUtilization.toFixed(1),
//       idleTeams,
//       avgEarningsPerPersonPerDay: avgEarningsPerPersonPerDay.toFixed(0),
//       teamsRegistered,
//       teamsActivated,
//       activationRate: activationRate.toFixed(1),
//       avgDaysToFirstJob: avgDaysToFirstJob.toFixed(1)
//     });
//   };

//   const categorizeByUtilization = (responseData) => {
//     if (!responseData || !responseData.data) return;

//     const buckets = {
//       '0-25': [],
//       '25-50': [],
//       '50-75': [],
//       '75-90': [],
//       '90+': []
//     };

//     responseData.data.forEach(m => {
//       const rate = m.performance?.completion_rate || 0;
      
//       if (rate >= 90) buckets['90+'].push(m);
//       else if (rate >= 75) buckets['75-90'].push(m);
//       else if (rate >= 50) buckets['50-75'].push(m);
//       else if (rate >= 25) buckets['25-50'].push(m);
//       else buckets['0-25'].push(m);
//     });

//     setUtilizationBuckets(buckets);
//   };

//   const findTopPerformers = (responseData) => {
//     if (!responseData || !responseData.data || responseData.data.length === 0) return;

//     const sorted = [...responseData.data].sort((a, b) => 
//       b.financial_summary.total_earnings_paid - a.financial_summary.total_earnings_paid
//     );

//     setTopPerformers({
//       highest: sorted[0],
//       lowest: sorted[sorted.length - 1]
//     });
//   };

//   const handleFilterChange = (key, value) => {
//     setFilters(prev => ({ ...prev, [key]: value }));
//   };

//   const applyFilters = () => {
//     fetchData();
//     setShowFilters(false);
//   };

//   const clearFilters = () => {
//     setFilters({
//       has_availability: '',
//       has_allocations: '',
//       village: '',
//       min_crew: '',
//       registered_by: ''
//     });
//     fetchData();
//   };

//   // Prepare map data
//   const getMapData = () => {
//     if (!data || !data.data) return { homeLocations: [], workLocations: [] };

//     const homeLocations = [];
//     const workLocations = [];
//     const locationCounts = {};

//     data.data.forEach(mukkadam => {
//       // Home location (if available)
//       if (mukkadam.village) {
//         const key = mukkadam.village;
//         if (!locationCounts[key]) {
//           locationCounts[key] = {
//             name: mukkadam.village,
//             type: 'home',
//             count: 0,
//             crews: 0
//           };
//         }
//         locationCounts[key].count++;
//         locationCounts[key].crews += mukkadam.crew_size;
//       }

//       // Work locations
//       mukkadam.allocations.all_allocations.forEach(allocation => {
//         if (allocation.job && allocation.job.location) {
//           const location = allocation.job.location;
//           const key = `work_${location}`;
//           if (!locationCounts[key]) {
//             locationCounts[key] = {
//               name: location,
//               type: 'work',
//               count: 0,
//               totalArea: 0
//             };
//           }
//           locationCounts[key].count++;
//           locationCounts[key].totalArea += allocation.allocated_area;
//         }
//       });
//     });

//     Object.values(locationCounts).forEach(loc => {
//       if (loc.type === 'home') {
//         homeLocations.push(loc);
//       } else {
//         workLocations.push(loc);
//       }
//     });

//     return { homeLocations, workLocations };
//   };

//   if (loading) {
//     return (
//       <div className="min-h-screen flex items-center justify-center bg-gray-50">
//         <div className="text-center">
//           <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
//           <p className="mt-4 text-gray-500 font-medium">Loading Active Teams...</p>
//         </div>
//       </div>
//     );
//   }

//   const mapData = getMapData();

//   return (
//     <div className="min-h-screen bg-gray-50 p-4 md:p-8">
//       <div className="max-w-7xl mx-auto space-y-6">
        
//         {/* Header */}
//         <div className="flex justify-between items-center">
//           <div>
//             <h1 className="text-3xl font-extrabold text-gray-900">Active Teams Dashboard</h1>
//             <p className="text-sm text-gray-500 mt-1">Real-time workforce analytics and performance tracking</p>
//           </div>
//           <button 
//             onClick={() => setShowFilters(!showFilters)}
//             className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
//           >
//             <Filter size={18} />
//             Filters
//           </button>
//         </div>

//         {/* Filter Panel */}
//         {showFilters && (
//           <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
//             <h3 className="text-lg font-bold text-gray-900 mb-4">Filter Active Teams</h3>
            
//             <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
//               <div>
//                 <label className="block text-sm font-medium text-gray-700 mb-2">
//                   Has Availability
//                 </label>
//                 <select
//                   value={filters.has_availability}
//                   onChange={(e) => handleFilterChange('has_availability', e.target.value)}
//                   className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
//                 >
//                   <option value="">All</option>
//                   <option value="true">Yes</option>
//                   <option value="false">No</option>
//                 </select>
//               </div>

//               <div>
//                 <label className="block text-sm font-medium text-gray-700 mb-2">
//                   Has Allocations
//                 </label>
//                 <select
//                   value={filters.has_allocations}
//                   onChange={(e) => handleFilterChange('has_allocations', e.target.value)}
//                   className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
//                 >
//                   <option value="">All</option>
//                   <option value="true">Yes</option>
//                   <option value="false">No</option>
//                 </select>
//               </div>

//               <div>
//                 <label className="block text-sm font-medium text-gray-700 mb-2">
//                   Village
//                 </label>
//                 <input
//                   type="text"
//                   value={filters.village}
//                   onChange={(e) => handleFilterChange('village', e.target.value)}
//                   placeholder="Search village..."
//                   className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
//                 />
//               </div>

//               <div>
//                 <label className="block text-sm font-medium text-gray-700 mb-2">
//                   Minimum Crew Size
//                 </label>
//                 <input
//                   type="number"
//                   value={filters.min_crew}
//                   onChange={(e) => handleFilterChange('min_crew', e.target.value)}
//                   placeholder="e.g., 20"
//                   className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
//                 />
//               </div>

//               <div>
//                 <label className="block text-sm font-medium text-gray-700 mb-2">
//                   Registered By (User ID)
//                 </label>
//                 <input
//                   type="number"
//                   value={filters.registered_by}
//                   onChange={(e) => handleFilterChange('registered_by', e.target.value)}
//                   placeholder="User ID"
//                   className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
//                 />
//               </div>
//             </div>

//             <div className="flex justify-end gap-3">
//               <button
//                 onClick={clearFilters}
//                 className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
//               >
//                 Clear All
//               </button>
//               <button
//                 onClick={applyFilters}
//                 className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
//               >
//                 Apply Filters
//               </button>
//             </div>
//           </div>
//         )}

//         {/* Key Metrics Grid */}
//         <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
//           <MetricCard 
//             title="Active Teams"
//             value={metrics.activeTeams}
//             icon={<Users className="text-indigo-600" />}
//             color="indigo"
//           />
//           <MetricCard 
//             title="Available Man Days"
//             value={metrics.availableManDays}
//             icon={<Calendar className="text-blue-600" />}
//             color="blue"
//           />
//           <MetricCard 
//             title="Avg Utilisation"
//             value={`${metrics.avgUtilization}%`}
//             icon={<TrendingUp className="text-green-600" />}
//             color="green"
//           />
//           <MetricCard 
//             title="Idle Teams"
//             value={metrics.idleTeams}
//             subtitle="< 25% utilization"
//             icon={<AlertCircle className="text-orange-600" />}
//             color="orange"
//           />
//           <MetricCard 
//             title="Avg ₹/Person/Day"
//             value={`₹${metrics.avgEarningsPerPersonPerDay}`}
//             icon={<DollarSign className="text-purple-600" />}
//             color="purple"
//           />
//           <MetricCard 
//             title="Teams Registered"
//             value={metrics.teamsRegistered}
//             icon={<CheckCircle className="text-teal-600" />}
//             color="teal"
//           />
//         </div>

//         {/* Activation Metrics */}
//         <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
//           <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
//             <Zap className="text-yellow-500" size={20} />
//             Team Activation Metrics
//           </h3>
//           <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
//             <div className="text-center">
//               <div className="text-4xl font-black text-indigo-600 mb-2">
//                 {metrics.teamsActivated}
//               </div>
//               <p className="text-sm text-gray-600 font-medium">Teams Activated</p>
//               <p className="text-xs text-gray-400 mt-1">Have received at least one job</p>
//             </div>
//             <div className="text-center">
//               <div className="text-4xl font-black text-green-600 mb-2">
//                 {metrics.activationRate}%
//               </div>
//               <p className="text-sm text-gray-600 font-medium">Activation Rate</p>
//               <p className="text-xs text-gray-400 mt-1">
//                 {metrics.teamsActivated} / {metrics.teamsRegistered} teams
//               </p>
//             </div>
//             <div className="text-center">
//               <div className="text-4xl font-black text-blue-600 mb-2">
//                 {metrics.avgDaysToFirstJob}
//               </div>
//               <p className="text-sm text-gray-600 font-medium">Avg Days to First Job</p>
//               <p className="text-xs text-gray-400 mt-1">From registration</p>
//             </div>
//           </div>
//         </div>

//         {/* Utilization & Idle Risk Analysis */}
//         <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
//           <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
//             <BarChart3 className="text-indigo-600" size={20} />
//             Utilisation & Idle Risk Distribution
//           </h3>
          
//           <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
//             {Object.entries(utilizationBuckets).map(([bucket, teams]) => (
//               <UtilizationBucket 
//                 key={bucket}
//                 label={`${bucket}%`}
//                 count={teams.length}
//                 total={data?.data?.length || 0}
//                 teams={teams}
//                 isRisk={bucket === '0-25'}
//               />
//             ))}
//           </div>
//         </div>

//         {/* Top & Bottom Performers */}
//         <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
//           {/* Highest Earning Team */}
//           <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl border-2 border-green-200 p-6">
//             <div className="flex items-center gap-2 mb-4">
//               <Award className="text-green-600" size={24} />
//               <h3 className="text-lg font-bold text-green-900">Highest Earning Team</h3>
//             </div>
            
//             {topPerformers.highest ? (
//               <div className="space-y-3">
//                 <div className="flex justify-between items-start">
//                   <div>
//                     <h4 className="text-xl font-black text-gray-900">
//                       {topPerformers.highest.mukkadam_name}
//                     </h4>
//                     <p className="text-sm text-gray-600 flex items-center gap-1 mt-1">
//                       <MapPin size={14} /> {topPerformers.highest.village}
//                     </p>
//                   </div>
//                   <div className="text-right">
//                     <div className="text-2xl font-black text-green-600">
//                       ₹{topPerformers.highest.financial_summary.total_earnings_paid.toLocaleString()}
//                     </div>
//                     <p className="text-xs text-gray-500">Total Earned</p>
//                   </div>
//                 </div>
                
//                 <div className="grid grid-cols-3 gap-2 pt-3 border-t border-green-200">
//                   <div className="text-center">
//                     <div className="text-lg font-bold text-gray-900">
//                       {topPerformers.highest.allocations.completed}
//                     </div>
//                     <p className="text-xs text-gray-600">Jobs Done</p>
//                   </div>
//                   <div className="text-center">
//                     <div className="text-lg font-bold text-gray-900">
//                       {topPerformers.highest.crew_size}
//                     </div>
//                     <p className="text-xs text-gray-600">Crew Size</p>
//                   </div>
//                   <div className="text-center">
//                     <div className="text-lg font-bold text-gray-900">
//                       {topPerformers.highest.performance.completion_rate}%
//                     </div>
//                     <p className="text-xs text-gray-600">Utilization</p>
//                   </div>
//                 </div>
//               </div>
//             ) : (
//               <p className="text-gray-500 text-center py-4">No data available</p>
//             )}
//           </div>

//           {/* Lowest Earning Team */}
//           <div className="bg-gradient-to-br from-orange-50 to-red-50 rounded-xl border-2 border-orange-200 p-6">
//             <div className="flex items-center gap-2 mb-4">
//               <Target className="text-orange-600" size={24} />
//               <h3 className="text-lg font-bold text-orange-900">Needs Attention</h3>
//             </div>
            
//             {topPerformers.lowest ? (
//               <div className="space-y-3">
//                 <div className="flex justify-between items-start">
//                   <div>
//                     <h4 className="text-xl font-black text-gray-900">
//                       {topPerformers.lowest.mukkadam_name}
//                     </h4>
//                     <p className="text-sm text-gray-600 flex items-center gap-1 mt-1">
//                       <MapPin size={14} /> {topPerformers.lowest.village}
//                     </p>
//                   </div>
//                   <div className="text-right">
//                     <div className="text-2xl font-black text-orange-600">
//                       ₹{topPerformers.lowest.financial_summary.total_earnings_paid.toLocaleString()}
//                     </div>
//                     <p className="text-xs text-gray-500">Total Earned</p>
//                   </div>
//                 </div>
                
//                 <div className="grid grid-cols-3 gap-2 pt-3 border-t border-orange-200">
//                   <div className="text-center">
//                     <div className="text-lg font-bold text-gray-900">
//                       {topPerformers.lowest.allocations.completed}
//                     </div>
//                     <p className="text-xs text-gray-600">Jobs Done</p>
//                   </div>
//                   <div className="text-center">
//                     <div className="text-lg font-bold text-gray-900">
//                       {topPerformers.lowest.crew_size}
//                     </div>
//                     <p className="text-xs text-gray-600">Crew Size</p>
//                   </div>
//                   <div className="text-center">
//                     <div className="text-lg font-bold text-gray-900">
//                       {topPerformers.lowest.performance.completion_rate}%
//                     </div>
//                     <p className="text-xs text-gray-600">Utilization</p>
//                   </div>
//                 </div>
//               </div>
//             ) : (
//               <p className="text-gray-500 text-center py-4">No data available</p>
//             )}
//           </div>
//         </div>

//         {/* Geographic Coverage Map */}
//         <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
//           <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
//             <MapIcon className="text-indigo-600" size={20} />
//             Geographic Coverage
//           </h3>
          
//           <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
//             {/* Home Base Locations */}
//             <div>
//               <h4 className="text-md font-bold text-gray-700 mb-3 flex items-center gap-2">
//                 <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
//                 Teams Based In
//               </h4>
//               <div className="space-y-2 max-h-64 overflow-y-auto">
//                 {mapData.homeLocations.map((loc, idx) => (
//                   <div key={idx} className="flex justify-between items-center p-3 bg-blue-50 rounded-lg">
//                     <div>
//                       <p className="font-bold text-gray-900">{loc.name}</p>
//                       <p className="text-xs text-gray-600">{loc.crews} total crew members</p>
//                     </div>
//                     <div className="text-right">
//                       <div className="text-lg font-black text-blue-600">{loc.count}</div>
//                       <p className="text-xs text-gray-500">teams</p>
//                     </div>
//                   </div>
//                 ))}
//                 {mapData.homeLocations.length === 0 && (
//                   <p className="text-gray-400 text-center py-4">No location data</p>
//                 )}
//               </div>
//             </div>

//             {/* Work Locations */}
//             <div>
//               <h4 className="text-md font-bold text-gray-700 mb-3 flex items-center gap-2">
//                 <div className="w-3 h-3 bg-green-500 rounded-full"></div>
//                 Areas Served
//               </h4>
//               <div className="space-y-2 max-h-64 overflow-y-auto">
//                 {mapData.workLocations.map((loc, idx) => (
//                   <div key={idx} className="flex justify-between items-center p-3 bg-green-50 rounded-lg">
//                     <div>
//                       <p className="font-bold text-gray-900">{loc.name}</p>
//                       <p className="text-xs text-gray-600">{loc.totalArea.toFixed(1)} acres worked</p>
//                     </div>
//                     <div className="text-right">
//                       <div className="text-lg font-black text-green-600">{loc.count}</div>
//                       <p className="text-xs text-gray-500">jobs</p>
//                     </div>
//                   </div>
//                 ))}
//                 {mapData.workLocations.length === 0 && (
//                   <p className="text-gray-400 text-center py-4">No work location data</p>
//                 )}
//               </div>
//             </div>
//           </div>

//           {/* Summary Stats */}
//           <div className="mt-6 pt-6 border-t border-gray-200">
//             <div className="grid grid-cols-3 gap-4 text-center">
//               <div>
//                 <div className="text-2xl font-black text-indigo-600">
//                   {mapData.homeLocations.length}
//                 </div>
//                 <p className="text-xs text-gray-600 mt-1">Base Villages</p>
//               </div>
//               <div>
//                 <div className="text-2xl font-black text-green-600">
//                   {mapData.workLocations.length}
//                 </div>
//                 <p className="text-xs text-gray-600 mt-1">Work Areas</p>
//               </div>
//               <div>
//                 <div className="text-2xl font-black text-purple-600">
//                   {mapData.homeLocations.length + mapData.workLocations.length}
//                 </div>
//                 <p className="text-xs text-gray-600 mt-1">Total Reach</p>
//               </div>
//             </div>
//           </div>
//         </div>

//       </div>
//     </div>
//   );
// };

// // Metric Card Component
// const MetricCard = ({ title, value, subtitle, icon, color }) => {
//   const colors = {
//     indigo: 'bg-indigo-50 border-indigo-200',
//     blue: 'bg-blue-50 border-blue-200',
//     green: 'bg-green-50 border-green-200',
//     orange: 'bg-orange-50 border-orange-200',
//     purple: 'bg-purple-50 border-purple-200',
//     teal: 'bg-teal-50 border-teal-200'
//   };

//   return (
//     <div className={`${colors[color]} rounded-xl border-2 p-6 hover:shadow-lg transition-all`}>
//       <div className="flex items-start justify-between mb-3">
//         <div className="p-2 bg-white rounded-lg shadow-sm">
//           {icon}
//         </div>
//       </div>
//       <div>
//         <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">
//           {title}
//         </p>
//         <p className="text-3xl font-black text-gray-900">
//           {value}
//         </p>
//         {subtitle && (
//           <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
//         )}
//       </div>
//     </div>
//   );
// };

// // Utilization Bucket Component
// const UtilizationBucket = ({ label, count, total, teams, isRisk }) => {
//   const percentage = total > 0 ? ((count / total) * 100).toFixed(0) : 0;
  
//   return (
//     <div className={`p-4 rounded-xl border-2 ${
//       isRisk 
//         ? 'bg-red-50 border-red-300' 
//         : 'bg-gray-50 border-gray-200'
//     } hover:shadow-md transition-all cursor-pointer`}>
//       <div className="text-center">
//         <p className="text-xs font-bold text-gray-500 uppercase mb-2">{label}</p>
//         <div className={`text-4xl font-black ${
//           isRisk ? 'text-red-600' : 'text-gray-900'
//         }`}>
//           {count}
//         </div>
//         <div className="mt-2 w-full bg-gray-200 h-2 rounded-full overflow-hidden">
//           <div 
//             className={`h-full ${isRisk ? 'bg-red-500' : 'bg-indigo-500'}`}
//             style={{ width: `${percentage}%` }}
//           />
//         </div>
//         <p className="text-xs text-gray-500 mt-2">{percentage}% of teams</p>
//       </div>
//     </div>
//   );
// };

// export default ActiveMukkadamsDashboard;