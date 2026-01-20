import React, { useState, useEffect ,useMemo} from 'react';
import axios from 'axios';
import {
  Users, Truck, X, Calendar, MapPin, TrendingUp,Edit,
  CheckCircle, AlertCircle, ArrowRight, Layers,ChevronDown,Search,Star, AlertTriangle,DollarSign,
  Users as UsersIcon, Award, Briefcase, Filter
} from 'lucide-react';
import { getAuthConfig } from './utils/auth';

// At the top, add state


// Import the component
import EditMukkadamModal from './EditModel';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_SUPPLY;
const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;
import type {
  Job,
  Activity,
  Allocation,
  Mukkadam,
  TransportProvider,
  MukkadamAllocation,
  TransportAllocation,
  ActivityLog,
  DailyStat
} from './types/allocation';

interface ComplexAllocationModalProps {
  job: Job;
  onClose: () => void;
  editMode?: boolean;
  existingAllocation?: Allocation | null;
  onSuccess: () => void;
  mukkadams: Mukkadam[];
  transportProviders: TransportProvider[];
}
interface RecommendationBuckets {
  all: any[];  // ✅ NEW
  overall_best: any[];
  available_on_date: any[];
  nearby_logistics: any[];
  farmer_history: any[];
  activity_experts: any[];
  high_volume: any[];
  new_local_recruits: any[];
  cost_effective: any[]; 
  transport_cost: any[];  // ✅ ADD 
}

// Add this helper for better UX
const getBucketLabel = (key: string): string => {
  const labels: Record<string, string> = {
    overall_best: 'Top Recommendations',
    available_on_date: 'Available on This Date',
    nearby_logistics: 'Working Nearby (±3 days)',
    farmer_history: 'Previously Worked for This Farmer',
    activity_experts: 'Activity Specialists',
    high_volume: 'High Volume Workers',
    new_local_recruits: 'New Local Recruits',
    cost_effective: 'Most Cost-Effective' , // ✅ ADD THIS
    transport_cost: 'Lowest Transport Cost'  // ✅ ADD
  };
  return labels[key] || key;
};
const ComplexAllocationModal: React.FC<ComplexAllocationModalProps> = ({
  job,
  onClose,
  onSuccess,
  mukkadams,
  transportProviders,
  editMode = false,
  existingAllocation = null
}) => {
  const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null);
  const [allocationForm, setAllocationForm] = useState({
    mukkadam_id: '',
    allocated_area: '',
    work_date: '',
    mukkadam_price: '',
    crew_size: '',
    transport_type: 'provider' as 'provider' | 'own' | 'none',
    transport_provider_id: '',
    own_transport_price: '',
    transport_price: ''
  });
  const [allocating, setAllocating] = useState(false);
  const [crewCapacity, setCrewCapacity] = useState<any>(null);
  const [isPriceTbd, setIsPriceTbd] = useState(false);

// Import the logic


  // Calculate auto-price when area changes
  useEffect(() => {
  // Only auto-calculate if NOT in TBD mode
  if (selectedActivity && allocationForm.allocated_area && !isPriceTbd) {
    const area = parseFloat(allocationForm.allocated_area);
    if (!isNaN(area) && area > 0) {
      const price = area * selectedActivity.rate_per_acre;
      setAllocationForm(prev => ({
        ...prev,
        mukkadam_price: price.toFixed(2)
      }));
    }
  }
}, [allocationForm.allocated_area, selectedActivity, isPriceTbd]);

// --- STATE ---
  const [recBuckets, setRecBuckets] = useState<RecommendationBuckets | null>(null);
  const [activeTab, setActiveTab] = useState<keyof RecommendationBuckets>('overall_best');
  const [loadingRecs, setLoadingRecs] = useState(false);
const [editingMukkadam, setEditingMukkadam] = useState<any>(null);
  // --- API CALL ---
// ComplexAllocationModal.tsx - Update the recommendation fetch

useEffect(() => {
  const fetchRecommendations = async () => {
    if (!selectedActivity || !allocationForm.work_date) return;

    try {
      setLoadingRecs(true);
      const payload = {
        work_date: allocationForm.work_date,
        farmer_id: job?.farmer_id || "",
        activity_name: selectedActivity.activity_name,
        location: `${job.farmer?.village || ''}, ${job.farmer?.taluka || ''}, ${job.farmer?.district || ''}`.trim(),

        job_latitude: job?.latitude ? parseFloat(String(job.latitude)) : null,
        job_longitude: job?.longitude ? parseFloat(String(job.longitude)) : null
      };

      const response = await axios.post(
        `${API_BASE_URL_A}/ap/detailed-recommendations/`, 
        payload, 
        
      );
      if (response.data) {
        setRecBuckets(response.data);
        setActiveTab('overall_best');
      }

    } catch (err) {
      console.error("Failed to fetch recommendations", err);
    } finally {
      setLoadingRecs(false);
    }
  };

  const timer = setTimeout(() => {
    fetchRecommendations();
  }, 300);

  return () => clearTimeout(timer);

}, [selectedActivity, allocationForm.work_date, job.farmer]);


  // Calculate crew capacity when mukkadam is selected OR crew_size changes
  useEffect(() => {
    if (allocationForm.mukkadam_id && selectedActivity) {
      const mukkadam = mukkadams.find(m => m.id === parseInt(allocationForm.mukkadam_id));
      if (mukkadam) {
        const crewSize = allocationForm.crew_size 
          ? parseInt(allocationForm.crew_size) 
          : parseInt(mukkadam.crew_size);
        
        const workersPerAcre = selectedActivity.estimated_workers / selectedActivity.total_area;
        const maxAreaPerDay = crewSize / workersPerAcre;
        
        setCrewCapacity({
          crew_size: crewSize,
          workers_per_acre: workersPerAcre.toFixed(1),
          max_area_per_day: maxAreaPerDay.toFixed(2)
        });

        // ✅ CHANGE: Don't auto-fill area in edit mode
        if (!editMode && !allocationForm.allocated_area) {
          const suggestedArea = Math.min(maxAreaPerDay, selectedActivity.remaining_area);
          setAllocationForm(prev => ({
            ...prev,
            allocated_area: suggestedArea.toFixed(2)
          }));
        }
      }
    }
  }, [allocationForm.mukkadam_id, allocationForm.crew_size, selectedActivity, editMode]);

  // ✅ Pre-fill form when in edit mode
  useEffect(() => {
    if (editMode && existingAllocation) {
      const activity = job.activities?.find(a => 
        a.activity_name === existingAllocation.activity_name
      );
      
      if (activity) {
        setSelectedActivity(activity);
        
        setAllocationForm({
          mukkadam_id: existingAllocation.mukkadam_id.toString(),
          allocated_area: existingAllocation.allocated_area?.toString() || '',
          work_date: existingAllocation.work_date || '',
          mukkadam_price: existingAllocation.mukkadam_price?.toString() || '',
          crew_size: existingAllocation.crew_size?.toString() || '',
          transport_type: existingAllocation.transport_type || 'provider',
          transport_provider_id: existingAllocation.transport_provider_id?.toString() || '',
          own_transport_price: existingAllocation.own_transport_price?.toString() || '',
          transport_price: existingAllocation.transport_price?.toString() || ''
        });
      }
    }
  }, [editMode, existingAllocation, job.activities]);

  const handleActivitySelect = (activity: Activity) => {
    setSelectedActivity(activity);
    setAllocationForm({
      mukkadam_id: '',
      allocated_area: '',
      work_date: activity.scheduled_date,
      mukkadam_price: '',
      crew_size: '',
      transport_type: 'provider',
      transport_provider_id: '',
      own_transport_price: '',
      transport_price: ''
    });
    setCrewCapacity(null);
  };

  // ✅ UPDATED: Handle both create and update
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedActivity) return;

    // Validation
    if (!allocationForm.mukkadam_id) {
      alert('Please select a mukkadam');
      return;
    }
    // Find the actual Mukkadam object to get their full crew size
    const mukkadamObj = mukkadams.find(m => m.id === parseInt(allocationForm.mukkadam_id));

    const finalCrewSize = allocationForm.crew_size 
      ? parseInt(allocationForm.crew_size) 
      : parseInt(mukkadamObj?.crew_size || '0');

    if (!allocationForm.allocated_area || parseFloat(allocationForm.allocated_area) <= 0) {
      alert('Please enter valid area');
      return;
    }
    
    // ✅ CHANGE: In edit mode, allow up to remaining + currently allocated area
    // ✅ CHANGE: In edit mode, allow up to remaining + currently allocated area
const maxAllowedArea = editMode && existingAllocation
  ? selectedActivity.remaining_area + parseFloat(String(existingAllocation.allocated_area || 0))
  : selectedActivity.remaining_area;
      
    if (parseFloat(allocationForm.allocated_area) > maxAllowedArea) {
      alert(`Cannot allocate more than ${maxAllowedArea.toFixed(2)} acres`);
      return;
    }
    
    if (allocationForm.transport_type === 'provider' && !allocationForm.transport_provider_id) {
      alert('Please select transport provider');
      return;
    }

    // Inside handleSubmit function...

    // if (allocationForm.transport_type === 'provider' && !allocationForm.transport_price) {
    //   alert('Please enter transport price');
    //   return;
    // }

    // --- 🟢 ADD THIS BLOCK ---
    if (!isPriceTbd && selectedActivity.total_price) {
      const enteredPrice = parseFloat(allocationForm.mukkadam_price);
      const maxAllowedPrice = selectedActivity.total_price * 1.15; // 90% limit

      if (enteredPrice > maxAllowedPrice) {
        alert(
          `⛔ Price Too High!\n\n` +
          `You entered: ₹${enteredPrice.toLocaleString()}\n` +
          `Limit (115%): ₹${maxAllowedPrice.toLocaleString()}\n\n` +
          `Not allowed. Please find someone better.`
        );
        return; 
      }
    }
    // --- 🟢 END OF NEW BLOCK ---


    if (allocationForm.transport_type === 'own' && !allocationForm.own_transport_price) {
      alert('Please enter own transport price');
      return;
    }
    if (allocationForm.transport_type === 'provider' && !allocationForm.transport_price) {
      alert('Please enter transport price');
      return;
    }

// Inside handleSubmit function...

    // ... (Existing Mukkadam check is here) ...

    // --- 🟢 ADD THIS NEW BLOCK: Overall Cost Validation ---
    if (!isPriceTbd && selectedActivity.total_price) {
      // 1. Calculate actual transport price based on type
      const activeTransportPrice = allocationForm.transport_type === 'provider' 
        ? (parseFloat(allocationForm.transport_price) || 0)
        : allocationForm.transport_type === 'own'
        ? (parseFloat(allocationForm.own_transport_price) || 0)
        : 0;

      // 2. Calculate total allocation cost
      const currentMukkadamPrice = parseFloat(allocationForm.mukkadam_price) || 0;
      const totalAllocationCost = currentMukkadamPrice + activeTransportPrice;
      
      // 3. Define the limit (90% of Revenue)
      const maxOverallLimit = selectedActivity.total_price * 1.155;

      if (totalAllocationCost > maxOverallLimit) {
        alert(
          `⛔ Total Cost Too High!\n\n` +
          `Mukkadam: ₹${currentMukkadamPrice.toLocaleString()}\n` +
          `Transport: ₹${activeTransportPrice.toLocaleString()}\n` +
          `Total: ₹${totalAllocationCost.toLocaleString()}\n\n` +
          `Limit (115% of Revenue): ₹${maxOverallLimit.toLocaleString()}\n` +
          `You are exceeding by ₹${(totalAllocationCost - maxOverallLimit).toLocaleString()}\n\n` +
          `Not allowed. Please find someone better to reduce costs.`
        );
        return;
      }
    }
    // --- 🟢 END OF NEW BLOCK ---

    setAllocating(true);

    try {
      // ✅ Use finalCrewSize in the notes
      let notes = `Activity ID: ${selectedActivity.activity_id}`;
    notes += `\nCrew Size: ${finalCrewSize} workers`;
    if (isPriceTbd) {
      notes += `\nPRICE STATUS: To Be Decided Later`;
    }
      const payload = {
        activity_id: selectedActivity.activity_id,
        job_id: job.work_id,
        activity_name: selectedActivity.activity_name,
        location: `${job.farmer?.village || ''}, ${job.farmer?.taluka || ''}, ${job.farmer?.district || ''}`.trim(),
        job_latitude: job?.latitude,      // ✅ ADD
        job_longitude: job?.longitude ,    // ✅ ADD
        activity_type: selectedActivity.activity_type,
        scheduled_datetime: selectedActivity.scheduled_date,
        total_area: selectedActivity.total_area,
        total_price: selectedActivity.total_price,
        // location: selectedActivity.location,
        estimated_workers: selectedActivity.estimated_workers,
        rate_per_acre: selectedActivity.rate_per_acre,
        mukkadam_id: parseInt(allocationForm.mukkadam_id),
        allocated_area: parseFloat(allocationForm.allocated_area),
        work_date: allocationForm.work_date,
        crew_size: finalCrewSize,
        mukkadam_price: isPriceTbd ? 0 : parseFloat(allocationForm.mukkadam_price),
        transport_type: allocationForm.transport_type,
        transport_provider_id: allocationForm.transport_type === 'provider' 
          ? parseInt(allocationForm.transport_provider_id) 
          : null,
        own_transport_price: allocationForm.transport_type === 'own'
          ? parseFloat(allocationForm.own_transport_price || '0')
          : null,
        transport_price: (() => {
          if (allocationForm.transport_type === 'provider') {
            return parseFloat(allocationForm.transport_price || '0');
          } else if (allocationForm.transport_type === 'own') {
            return parseFloat(allocationForm.own_transport_price || '0');
          }
          return 0;
        })(),
        notes: notes
      };

      const config = getAuthConfig();
      let response;

      // ✅ NEW: Use PATCH for edit, POST for create
      if (editMode && existingAllocation) {
        response = await axios.patch(
          `${API_BASE_URL_A}/ap/allocations/${existingAllocation.id}/`,
          payload,
          config
        );
        alert(`✅ Allocation updated successfully!\n${response.data.message || ''}`);
      } else {
        response = await axios.post(
          `${API_BASE_URL_A}/ap/allocations/`,
          payload,
          config
        );
        alert(`✅ Allocated ${allocationForm.allocated_area} acres successfully!\n${response.data.message || ''}`);
      }

      onSuccess();
      
      // ✅ CHANGE: Close modal if editing, otherwise reset form
      if (editMode) {
        onClose();
      } else {
        // Reset form but keep activity selected
        setAllocationForm({
          mukkadam_id: '',
          allocated_area: '',
          work_date: selectedActivity.scheduled_date,
          mukkadam_price: '',
          crew_size: '',
          transport_type: 'provider',
          transport_provider_id: '',
          own_transport_price: '',
          transport_price: ''
        });
        setCrewCapacity(null);
      }

    } catch (error: any) {
      console.error('Allocation error:', error);
      alert(`Failed to ${editMode ? 'update' : 'allocate'}: ` + (error.response?.data?.error || error.message));
    } finally {
      setAllocating(false);
    }
  };

  const [mukkadamSearch, setMukkadamSearch] = useState('');
const [transportSearch, setTransportSearch] = useState('');
const [isMukkadamOpen, setIsMukkadamOpen] = useState(false);
const [isTransportOpen, setIsTransportOpen] = useState(false);
// 2. Add this logic before the return statement
  // --- FILTER LOGIC ---
const filteredMukkadams = useMemo(() => {
  let sourceList: any[] = [];

  if (recBuckets) {
    sourceList = recBuckets[activeTab] || [];
  } else {
    sourceList = mukkadams;
  }

  return sourceList.filter((m: any) => 
    m.mukkadam_name.toLowerCase().includes(mukkadamSearch.toLowerCase()) ||
    (m.village || "").toLowerCase().includes(mukkadamSearch.toLowerCase())
  );
}, [recBuckets, activeTab, mukkadams, mukkadamSearch]);

const filteredProviders = useMemo(() => {
  return [...transportProviders]
    .filter(p => 
      p.name.toLowerCase().includes(transportSearch.toLowerCase()) ||
      p.base_location?.toLowerCase().includes(transportSearch.toLowerCase())
    )
    .sort((a, b) => a.name.localeCompare(b.name));
}, [transportProviders, transportSearch]);

  const selectedMukkadam = mukkadams.find(m => m.id === parseInt(allocationForm.mukkadam_id));
  const selectedProvider = transportProviders.find(p => p.id === parseInt(allocationForm.transport_provider_id));

  const totalCost = (parseFloat(allocationForm.mukkadam_price) || 0) + 
    (allocationForm.transport_type === 'provider' 
      ? (parseFloat(allocationForm.transport_price) || 0)
      : allocationForm.transport_type === 'own'
      ? (parseFloat(allocationForm.own_transport_price) || 0)
      : 0);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-y-auto">
        {/* ✅ UPDATED: Header shows edit vs create */}
        <div className="bg-gradient-to-r from-green-600 to-blue-600 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
          <div>
            <h2 className="text-2xl font-bold text-white">
              {editMode ? 'Edit Allocation' : 'Allocate Complex Job'}
            </h2>
            <p className="text-white text-sm opacity-90">{job.work_id} - {job.title}</p>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:bg-white hover:bg-opacity-20 p-2 rounded-full transition"
          >
            <X size={24} />
          </button>
        </div>

        <div className="p-6">
          {/* Farmer Details */}
          {job.farmer && (
            <div className="mb-6 bg-gradient-to-r from-purple-50 to-indigo-50 p-4 rounded-xl border-2 border-purple-200">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-gray-900 mb-2 flex items-center">
                    <Users className="mr-2 text-purple-600" size={20} />
                    Farmer Details
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <div>
                      <p className="text-gray-600">Name</p>
                      <p className="font-semibold text-gray-900">{job.farmer.farmer_name}</p>
                    </div>
                    <div>
                      <p className="text-gray-600">Phone</p>
                      <p className="font-semibold text-gray-900">{job.farmer.phone_number}</p>
                    </div>
                    <div className="col-span-2">
                      <p className="text-gray-600">Location</p>
                      <p className="font-semibold text-gray-900">{job.farmer.location}</p>
                    </div>
                  </div>
                </div>
                
                <div className="ml-4 bg-white p-4 rounded-lg border-2 border-green-300 min-w-[200px]">
                  <p className="text-xs text-gray-600 mb-1">Total Job Value</p>
                  <p className="text-2xl font-bold text-green-600">
                    ₹{(job.booking?.total_amount || 0).toLocaleString()}
                  </p>
                  <div className="mt-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Advance:</span>
                      <span className="font-semibold text-blue-600">
                        ₹{(job.booking?.advance_paid || 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-gray-600">Balance:</span>
                      <span className="font-semibold text-orange-600">
                        ₹{(job.booking?.balance || 0).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left: Activities List */}
            <div className="lg:col-span-1">
              <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                <Layers className="mr-2 text-blue-600" />
                Activities ({job.activities?.length || 0})
              </h3>
              
              {/* ✅ UPDATED: Show info message in edit mode */}
              {editMode && (
                <div className="mb-4 bg-yellow-50 p-3 rounded-lg border border-yellow-200">
                  <p className="text-xs text-yellow-800">
                    📝 You are editing an existing allocation. The activity cannot be changed.
                  </p>
                </div>
              )}
              
              <div className="space-y-3">
                {job.activities?.map((activity) => (
                    <button
                      key={activity.activity_id || activity.id} // ✅ Use activity_id for key
                      onClick={() => handleActivitySelect(activity)}
                      className={`w-full text-left p-4 rounded-lg border-2 transition ${
                        selectedActivity?.activity_id === activity.activity_id  // ✅ CHANGE THIS LINE
                          ? 'border-blue-500 bg-blue-50'
                          : activity.is_fully_allocated
                          ? 'border-green-300 bg-green-50'
                          : 'border-gray-200 bg-white hover:border-blue-300'
                      }`}
                    disabled={
                      activity.is_fully_allocated || 
                      (editMode && selectedActivity?.id !== activity.id)  // ✅ NEW: Disable other activities in edit mode
                    }
                  >
                    <div className="flex items-start justify-between mb-2">
                      <span className="font-semibold text-gray-900 text-sm">
                        {activity.activity_name}
                      </span>
                      {activity.is_fully_allocated ? (
                        <CheckCircle size={18} className="text-green-600 flex-shrink-0" />
                      ) : (
                        <AlertCircle size={18} className="text-yellow-600 flex-shrink-0" />
                      )}
                    </div>
                    
                    <div className="space-y-1 text-xs text-gray-600">
                      {/* <div className="flex items-center">
                        <MapPin size={12} className="mr-1" />
                        {activity.location}
                      </div> */}
                      <div className="flex items-center">
                        <Calendar size={12} className="mr-1" />
                        {new Date(activity.scheduled_date).toLocaleDateString()}
                      </div>
                      <div className="flex items-center">
                        <TrendingUp size={12} className="mr-1" />
                        {activity.allocated_area}/{activity.total_area} acres
                      </div>
                      <div className="flex items-center justify-between pt-1 border-t border-gray-300">
                        <span className="text-green-600 font-semibold">₹{activity.total_price?.toLocaleString() || 0}</span>
                      </div>
                    </div>

                    {!activity.is_fully_allocated && (
                      <div className="mt-2">
                        <div className="bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full transition-all"
                            style={{
                              width: `${(activity.allocated_area / activity.total_area) * 100}%`
                            }}
                          />
                        </div>
                        <p className="text-xs text-gray-600 mt-1">
                          {activity.remaining_area.toFixed(2)} acres remaining
                        </p>
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Right: Allocation Form */}
            <div className="lg:col-span-2">
              {!selectedActivity ? (
                <div className="flex items-center justify-center h-full text-gray-500">
                  <div className="text-center">
                    <Layers size={48} className="mx-auto mb-4 opacity-50" />
                    <p>Select an activity to allocate</p>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-6">
                  
                  {/* Activity Info */}
                  <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                    <h4 className="font-bold text-blue-900 mb-3 flex items-center justify-between">
                      <span>{selectedActivity.activity_name}</span>
                      <span className="text-sm bg-green-100 text-green-700 px-3 py-1 rounded-full">
                        Revenue: ₹{selectedActivity.total_price?.toLocaleString() || 0}
                      </span>
                    </h4>
                    
                    <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                      <div>
                        <span className="text-gray-600">Location:</span>
                        <span className="font-semibold ml-2">{selectedActivity.location}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Date:</span>
                        <span className="font-semibold ml-2">
                          {new Date(selectedActivity.scheduled_date).toLocaleDateString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-600">Total Area:</span>
                        <span className="font-semibold ml-2">{selectedActivity.total_area} acres</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Remaining:</span>
                        <span className="font-semibold ml-2 text-orange-600">
                          {selectedActivity.remaining_area.toFixed(2)} acres
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-600">Rate:</span>
                        <span className="font-semibold ml-2">₹{selectedActivity.rate_per_acre}/acre</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Workers Needed:</span>
                        <span className="font-semibold ml-2">{selectedActivity.estimated_workers}</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2 pt-3 border-t border-blue-300">
                      <div className="bg-white p-2 rounded">
                        <p className="text-xs text-gray-600">Expected Revenue</p>
                        <p className="text-sm font-bold text-green-600">
                          ₹{selectedActivity.total_price?.toLocaleString() || 0}
                        </p>
                      </div>
                      <div className="bg-white p-2 rounded">
                        <p className="text-xs text-gray-600">Expected Transport</p>
                        <p className="text-sm font-bold text-orange-600">
                          ₹{selectedActivity.transport_cost?.toLocaleString() || 0}
                        </p>
                      </div>
                      <div className="bg-white p-2 rounded">
                        <p className="text-xs text-gray-600">Other Costs</p>
                        <p className="text-sm font-bold text-gray-600">
                          ₹{selectedActivity.other_cost?.toLocaleString() || 0}
                        </p>
                      </div>
                    </div>
                  </div>

{/* Mukkadam Selection */}
{/* Added relative here to anchor the dropdown */}
  <h3 className="text-lg font-bold text-gray-900 flex items-center border-b-2 border-indigo-200 pb-2">
    <Users className="mr-2 text-indigo-500" /> Mukkadam & Area
  </h3>

  <div>
    <label className="block text-sm font-medium text-gray-700 mb-2">
      Select Mukkadam <span className="text-red-500">*</span>
    </label>
    
    <div className="relative">
      {/* Trigger Button */}
      <div
        className="w-full px-3 py-2.5 border-2 border-gray-300 rounded-lg bg-white cursor-pointer flex justify-between items-center hover:border-indigo-400 transition-all"
        onClick={() => setIsMukkadamOpen(!isMukkadamOpen)}
      >
        <span className={selectedMukkadam ? "text-gray-900 font-semibold text-xs" : "text-gray-400 text-xs"}>
          {selectedMukkadam
            ? `✅ ${selectedMukkadam.mukkadam_name} • ${selectedMukkadam.village} • ${selectedMukkadam.crew_size}👥`
            : "Search or Select Mukkadam..."
          }
        </span>
        <ChevronDown
          size={18}
          className={`text-gray-400 transition-transform ${isMukkadamOpen ? 'rotate-180 text-indigo-600' : ''}`}
        />
      </div>

      {/* Dropdown */}
      {isMukkadamOpen && (
        <div className="absolute top-full left-0 right-0 z-[60] mt-2 bg-white border-2 border-gray-300 rounded-xl shadow-2xl flex flex-col max-h-[550px] w-full">
          
          {/* ✅ FIXED: Unified Sticky Header Wrapper (Contains Search + Tabs) */}
          <div className="sticky top-0 z-20 bg-white border-b border-gray-200 shadow-sm">
            
            {/* Search Bar */}
            <div className="p-3 bg-gradient-to-r from-gray-50 to-white">
              <div className="relative">
                <Search size={18} className="absolute left-3 top-3 text-gray-400" />
                <input
                  type="text"
                  autoFocus
                  placeholder="Search by name or village..."
                  className="w-full pl-10 pr-4 py-2.5 text-sm border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                  value={mukkadamSearch}
                  onChange={(e) => setMukkadamSearch(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
              </div>
            </div>

            {/* Category Tabs */}
            {recBuckets && (
              <div className="overflow-x-auto px-2 py-2 bg-gradient-to-r from-indigo-50 via-purple-50 to-pink-50 border-t border-indigo-100">
                <div className="flex gap-1.5 min-w-max">
                  {[
                    { id: 'all', label: 'All', icon: Filter, color: 'gray' },
                    { id: 'overall_best', label: 'Top', icon: Star, color: 'indigo' },
                    { id: 'cost_effective', label: 'Cost', icon: DollarSign, color: 'green' },
                    { id: 'transport_cost', label: 'Transport', icon: Truck, color: 'gray' },
                    { id: 'nearby_logistics', label: 'Nearby', icon: MapPin, color: 'blue' },
                    { id: 'farmer_history', label: 'Known', icon: UsersIcon, color: 'purple' },
                    { id: 'activity_experts', label: 'Expert', icon: Award, color: 'orange' },
                    { id: 'available_on_date', label: 'Free', icon: Calendar, color: 'green' },
                  ].map((tab) => {
                    const count = recBuckets[tab.id as keyof RecommendationBuckets]?.length || 0;
                    const isActive = activeTab === tab.id;
                    const Icon = tab.icon;

                    return (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveTab(tab.id as any);
                        }}
                        disabled={count === 0 && tab.id !== 'all'}
                        className={`
                          flex items-center gap-1 flex-shrink-0 px-2.5 py-1.5 rounded-md text-[11px] font-bold transition-all
                          ${isActive
                            ? `bg-${tab.color}-600 text-white shadow-md`
                            : `bg-white text-${tab.color}-700 hover:bg-${tab.color}-50 border border-${tab.color}-200`
                          }
                          ${count === 0 && tab.id !== 'all' ? 'opacity-30 cursor-not-allowed' : ''}
                        `}
                      >
                        <Icon size={12} />
                        {tab.label}
                        {count > 0 && (
                          <span className={`px-1 py-0.5 rounded text-[9px] font-bold ${isActive ? 'bg-white/30' : `bg-${tab.color}-100`}`}>
                            {count}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Mukkadam List - Scrollable Area */}
          <div className="overflow-y-auto flex-1 divide-y divide-gray-100 bg-white">
            {loadingRecs && (
              <div className="p-8 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-4 border-indigo-600 border-t-transparent mx-auto mb-2"></div>
                <p className="text-gray-500 text-xs font-medium">Analyzing mukkadams...</p>
              </div>
            )}

            {!loadingRecs && filteredMukkadams.length > 0 ? (
              filteredMukkadams.map((m: any) => {
                const isSelected = allocationForm.mukkadam_id === m.id.toString();
                const isBlocked = m.is_blocked;
                const isNew = recBuckets?.new_local_recruits?.some((nm: any) => nm.id === m.id);
                const score = m.recommendation_score || 0;

                return (
                  <div
                    key={m.id}
                    className={`
                      px-4 py-2.5 cursor-pointer transition-all duration-150
                      ${isSelected
                        ? 'bg-gradient-to-r from-indigo-50 to-purple-50 border-l-4 border-l-indigo-600'
                        : 'hover:bg-gray-50 border-l-4 border-l-transparent hover:border-l-gray-300'
                      }
                    `}
                    onClick={() => {
                      if (isBlocked) {
                        const confirmed = window.confirm(
                          `⚠️ WARNING: ${m.mukkadam_name} is already booked on this date.\n\nDo you still want to select them?`
                        );
                        if (!confirmed) return;
                      }

                      setAllocationForm({ ...allocationForm, mukkadam_id: m.id.toString() });
                      setIsMukkadamOpen(false);
                      setMukkadamSearch('');
                    }}
                  >
                    <div className="flex justify-between items-start gap-3">
                      <div className="flex-1 min-w-0">
                        {/* Name & Status */}
                        <div className="flex items-center gap-1.5 mb-1">
                          <h4 className="font-bold text-sm text-gray-900 truncate">
                            {m.mukkadam_name}
                          </h4>
                          {isSelected && <CheckCircle size={12} className="text-indigo-600 flex-shrink-0" />}
                          {isNew && <span className="px-1.5 py-0.5 bg-green-500 text-white text-[9px] font-bold rounded">NEW</span>}
                          {isBlocked && <span className="px-1.5 py-0.5 bg-red-500 text-white text-[9px] font-bold rounded animate-pulse">BOOKED</span>}
                        </div>

                        {/* Location */}
                        <div className="flex items-center gap-2 text-[10px] text-gray-600 mb-1">
                          <span className="flex items-center gap-0.5 truncate max-w-[200px]">
                            <MapPin size={10} className="text-gray-400 flex-shrink-0" />
                            {m.village || m.taluka || m.district || 'Unknown'}
                          </span>
                          <span className="w-1 h-1 rounded-full bg-gray-300 flex-shrink-0"></span>
                          <span className="flex items-center gap-0.5 flex-shrink-0">
                            <Users size={10} className="text-gray-400" />
                            {m.crew_size}
                          </span>
                        </div>

                        {/* Price Metrics */}
                        {m.price_metrics && m.price_metrics.price_display !== 'N/A' && (
                          <div className="flex items-center gap-1 mb-1 text-[10px]">
                            {m.price_metrics.asking_price && (
                              <span className={`px-1.5 py-0.5 rounded font-semibold ${m.price_metrics.is_base_price
                                  ? 'bg-gray-100 text-gray-700'
                                  : 'bg-green-100 text-green-700'
                                }`}>
                                ₹{m.price_metrics.asking_price.toFixed(0)} {m.price_metrics.is_base_price ? '(Base)' : '(Asked)'}
                              </span>
                            )}
                            {m.price_metrics.historical_price_per_acre && (
                              <span className="px-1.5 py-0.5 rounded font-semibold bg-blue-100 text-blue-700">
                                ₹{m.price_metrics.historical_price_per_acre.toFixed(0)}/ac (Hist)
                              </span>
                            )}
                          </div>
                        )}
                        
                        {/* Transport Cost Badge */}
                        {m.transport_cost && m.transport_cost.estimated_cost && (
                          <div className="bg-cyan-50 border border-cyan-200 rounded px-2 py-1 mb-1 inline-block">
                            <div className="flex items-center gap-1 text-[10px]">
                              <Truck size={10} className="text-cyan-600" />
                              <span className="font-bold text-cyan-700">
                                ₹{m.transport_cost.estimated_cost.toFixed(0)}
                              </span>
                              <span className="text-cyan-600">
                                ({m.transport_cost.distance_km}km)
                              </span>
                            </div>
                          </div>
                        )}

                        {/* Recommendation Tags */}
                        {m.recommendation_reasons && m.recommendation_reasons.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {m.recommendation_reasons.slice(0, 3).map((reason: string, idx: number) => {
                              let colorClass = 'bg-gray-100 text-gray-700';
                              if (reason.includes('⛔')) colorClass = 'bg-red-100 text-red-700';
                              else if (reason.includes('✅')) colorClass = 'bg-green-100 text-green-700';
                              else if (reason.includes('⭐')) colorClass = 'bg-yellow-100 text-yellow-800';
                              else if (reason.includes('🚚')) colorClass = 'bg-blue-100 text-blue-700';

                              return (
                                <span
                                  key={idx}
                                  className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${colorClass}`}
                                >
                                  {reason}
                                </span>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      {/* Score Badge */}
                      {score > 0 && (
                        <div
                          className={`
                            flex items-center gap-1 px-2 py-1 rounded-md font-bold text-[10px] shadow-sm flex-shrink-0
                            ${score >= 150
                              ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white'
                              : score >= 100
                                ? 'bg-gradient-to-r from-blue-500 to-indigo-500 text-white'
                                : 'bg-indigo-100 text-indigo-700'
                            }
                          `}
                        >
                          <Star size={10} className={score >= 100 ? 'fill-current' : ''} />
                          {Math.floor(score)}
                        </div>
                      )}

                       {/* Edit Button */}
                        {activeTab === 'all' && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingMukkadam(m);
                            }}
                            className="flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-700 hover:bg-purple-200 rounded text-[9px] font-bold transition ml-1"
                          >
                            <Edit size={10} />
                          </button>
                        )}
                    </div>
                  </div>
                );
              })
            ) : (
              !loadingRecs && (
                <div className="p-12 text-center">
                  <Users size={48} className="mx-auto mb-3 text-gray-300" />
                  <p className="text-gray-500 font-semibold text-sm">No mukkadams found</p>
                  <p className="text-gray-400 text-xs mt-1">Try adjusting your filters</p>
                </div>
              )
            )}
          </div>

          {/* Footer */}
          {!loadingRecs && filteredMukkadams.length > 0 && (
            <div className="px-5 py-3 bg-gray-50 border-t-2 border-gray-100 flex justify-between items-center text-xs rounded-b-xl">
              <span className="text-gray-600">
                Showing <span className="font-bold text-gray-900">{filteredMukkadams.length}</span> results
              </span>
              <span className="text-gray-500 font-medium truncate ml-2">
                {activeTab === 'all' ? 'All Mukkadams' : getBucketLabel(activeTab)}
              </span>
            </div>
          )}
        </div>
      )}
      
    </div>


    {selectedMukkadam && (
                        <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-200 mt-3">
                          <h4 className="font-semibold text-gray-700 mb-2">Selected Mukkadam:</h4>
                          <div className="grid grid-cols-2 gap-3 text-sm">
                            <div>
                              <span className="text-gray-600">Name:</span>
                              <span className="font-semibold ml-2">{selectedMukkadam.mukkadam_name}</span>
                            </div>
                            <div>
                              <span className="text-gray-600">Mobile:</span>
                              <span className="font-semibold ml-2">{selectedMukkadam.mobile_numbers}</span>
                            </div>
                            <div>
                              <span className="text-gray-600">Village:</span>
                              <span className="font-semibold ml-2">{selectedMukkadam.village}</span>
                            </div>
                            <div>
                              <span className="text-gray-600">Default Crew Size:</span>
                              <span className="font-semibold ml-2">{selectedMukkadam.crew_size}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {selectedMukkadam && (
                        <div className="mt-3">
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Crew Size for This Job
                            <span className="text-gray-500 font-normal ml-2">(Optional - defaults to {selectedMukkadam.crew_size})</span>
                          </label>
                          <input
                            type="number"
                            min="1"
                            max="200"
                            value={allocationForm.crew_size}
                            onChange={(e) => setAllocationForm({...allocationForm, crew_size: e.target.value})}
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                            placeholder={`Default: ${selectedMukkadam.crew_size} workers`}
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            💡 Override if mukkadam is bringing a different number of workers for this specific job
                          </p>
                        </div>
                      )}
                    </div>

                    {crewCapacity && (
                      <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-200">
                        <h4 className="font-semibold text-gray-700 mb-2">
                          Crew Capacity Analysis
                          {allocationForm.crew_size && (
                            <span className="ml-2 text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
                              Custom Size
                            </span>
                          )}
                        </h4>
                        <div className="grid grid-cols-3 gap-3 text-sm">
                          <div>
                            <p className="text-gray-600">Crew Size</p>
                            <p className="font-bold text-indigo-600">{crewCapacity.crew_size} workers</p>
                          </div>
                          <div>
                            <p className="text-gray-600">Workers/Acre</p>
                            <p className="font-bold text-indigo-600">{crewCapacity.workers_per_acre}</p>
                          </div>
                          <div>
                            <p className="text-gray-600">Max Area/Day</p>
                            <p className="font-bold text-green-600">{crewCapacity.max_area_per_day} acres</p>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Area to Allocate (acres) <span className="text-red-500">*</span>
                        </label>
                        <input
  required
  type="number"
  step="0.01"
  min="0.01"
  max={editMode && existingAllocation 
    ? selectedActivity.remaining_area + parseFloat(String(existingAllocation.allocated_area || 0))
    : selectedActivity.remaining_area}
  value={allocationForm.allocated_area}
  onChange={(e) => setAllocationForm({...allocationForm, allocated_area: e.target.value})}
  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
  placeholder="5.00"
/>
                        <p className="text-xs text-gray-500 mt-1">
  Max: {(editMode && existingAllocation 
    ? selectedActivity.remaining_area + parseFloat(String(existingAllocation.allocated_area || 0))
    : selectedActivity.remaining_area).toFixed(2)} acres
</p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Work Date <span className="text-red-500">*</span>
                        </label>
                        <input
                          required
                          type="date"
                          value={allocationForm.work_date}
                          onChange={(e) => setAllocationForm({...allocationForm, work_date: e.target.value})}
                          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                    </div>

                    <div>
{/* ... inside the render, locate the Mukkadam Price section ... */}

<div>
  <div className="flex justify-between items-center mb-2">
    <label className="block text-sm font-medium text-gray-700">
      Mukkadam Price (₹) <span className="text-red-500">*</span>
    </label>
    <label className="flex items-center text-xs font-semibold text-indigo-600 cursor-pointer">
      <input
        type="checkbox"
        className="mr-1 rounded border-gray-300"
        checked={isPriceTbd}
        onChange={(e) => {
          setIsPriceTbd(e.target.checked);
          if (e.target.checked) {
            setAllocationForm(prev => ({ ...prev, mukkadam_price: '0' }));
          }
        }}
      />
      To Be Decided Later
    </label>
  </div>

  <div className="relative">
    <span className="absolute left-4 top-3 text-gray-500 font-semibold">₹</span>
    <input
      required={!isPriceTbd}
      disabled={isPriceTbd}
      type="number"
      step="0.01"
      min="0"
      value={isPriceTbd ? "" : allocationForm.mukkadam_price}
      onChange={(e) => setAllocationForm({...allocationForm, mukkadam_price: e.target.value})}
      // 🟢 CHANGED: Add conditional styling for error state
      className={`w-full pl-8 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-indigo-500 ${
        isPriceTbd 
          ? 'bg-gray-100 text-gray-400 italic' 
          : (!isPriceTbd && selectedActivity && parseFloat(allocationForm.mukkadam_price) > (selectedActivity.total_price || 0) * 1.15)
            ? 'border-red-500 text-red-600 focus:ring-red-500 bg-red-50' // Error style
            : 'bg-white border-gray-300'
      }`}
      placeholder={isPriceTbd ? "Price will be decided later" : "Auto-calculated"}
    />
  </div>

  {/* 🟢 ADD THIS: Error Message Display */}
  {!isPriceTbd && selectedActivity && parseFloat(allocationForm.mukkadam_price) > (selectedActivity.total_price || 0) * 1.15 && (
    <div className="mt-2 text-xs font-bold text-red-600 flex items-center animate-pulse">
      <AlertTriangle size={14} className="mr-1" />
      <span>
        Not allowed. Limit is ₹{((selectedActivity.total_price || 0) * 1.15).toLocaleString()}. Please find someone better.
      </span>
    </div>
  )}
</div>
</div>
                  



                  {/* Transport Selection */}
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-gray-900 flex items-center border-b-2 border-orange-200 pb-2">
                      <Truck className="mr-2 text-orange-500" /> Transport Details
                    </h3>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Transport Type <span className="text-red-500">*</span>
                      </label>
                      <div className="grid grid-cols-3 gap-3">
                        <button
                          type="button"
                          onClick={() => setAllocationForm({...allocationForm, transport_type: 'provider', own_transport_price: '', transport_price: ''})}
                          className={`p-3 rounded-lg border-2 text-sm font-medium transition ${
                            allocationForm.transport_type === 'provider'
                              ? 'border-orange-500 bg-orange-50 text-orange-700'
                              : 'border-gray-300 text-gray-600 hover:border-orange-300'
                          }`}
                        >
                          Transport Provider
                        </button>
                        <button
                          type="button"
                          onClick={() => setAllocationForm({...allocationForm, transport_type: 'own', transport_provider_id: '', transport_price: ''})}
                          className={`p-3 rounded-lg border-2 text-sm font-medium transition ${
                            allocationForm.transport_type === 'own'
                              ? 'border-blue-500 bg-blue-50 text-blue-700'
                              : 'border-gray-300 text-gray-600 hover:border-blue-300'
                          }`}
                        >
                          Own Transport
                        </button>
                        <button
                          type="button"
                          onClick={() => setAllocationForm({...allocationForm, transport_type: 'none', transport_provider_id: '', own_transport_price: '', transport_price: ''})}
                          className={`p-3 rounded-lg border-2 text-sm font-medium transition ${
                            allocationForm.transport_type === 'none'
                              ? 'border-gray-500 bg-gray-50 text-gray-700'
                              : 'border-gray-300 text-gray-600 hover:border-gray-400'
                          }`}
                        >
                          No Transport
                        </button>
                      </div>
                    </div>

                    {allocationForm.transport_type === 'provider' && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Select Transport Provider <span className="text-red-500">*</span>
                          </label>
                          <div className="relative">
  <div 
    className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-white cursor-pointer flex justify-between items-center"
    onClick={() => setIsTransportOpen(!isTransportOpen)}
  >
    <span className={selectedProvider ? "text-gray-900 font-semibold" : "text-gray-400"}>
      {selectedProvider ? `${selectedProvider.name} - ${selectedProvider.base_location}` : "-- Search or Select Provider --"}
    </span>
    <ChevronDown size={18} className={`text-gray-400 transition-transform ${isTransportOpen ? 'rotate-180' : ''}`} />
  </div>

  {isTransportOpen && (
    <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-xl overflow-hidden">
      <div className="p-2 border-b bg-gray-50 sticky top-0">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-2.5 text-gray-400" />
          <input 
            type="text"
            autoFocus
            placeholder="Search provider..."
            className="w-full pl-10 pr-4 py-2 text-sm border rounded focus:ring-2 focus:ring-orange-500 outline-none"
            value={transportSearch}
            onChange={(e) => setTransportSearch(e.target.value)}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      </div>
      <div className="max-h-48 overflow-y-auto">
        {filteredProviders.map(p => (
          <div 
            key={p.id}
            className={`px-4 py-2.5 text-sm hover:bg-orange-50 cursor-pointer border-b last:border-0 ${allocationForm.transport_provider_id === p.id.toString() ? 'bg-orange-50 font-bold' : ''}`}
            onClick={() => {
              setAllocationForm({...allocationForm, transport_provider_id: p.id.toString()});
              setIsTransportOpen(false);
              setTransportSearch('');
            }}
          >
            {p.name} <span className="text-xs text-gray-500 ml-2">({p.base_location})</span>
          </div>
        ))}
      </div>
    </div>
  )}
</div>
                        </div>

                        {selectedProvider && (
                          <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                            <h4 className="font-semibold text-gray-700 mb-2">Selected Provider:</h4>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                              <div>
                                <span className="text-gray-600">Name:</span>
                                <span className="font-semibold ml-2">{selectedProvider.name}</span>
                              </div>
                              <div>
                                <span className="text-gray-600">Contact:</span>
                                <span className="font-semibold ml-2">{selectedProvider.contact_number}</span>
                              </div>
                            </div>
                          </div>
                        )}

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Transport Price (₹) <span className="text-red-500">*</span>
                          </label>
                          <div className="relative">
                            <span className="absolute left-4 top-3 text-gray-500 font-semibold">₹</span>
                            <input
                              required
                              type="number"
                              step="0.01"
                              min="0"
                              value={allocationForm.transport_price}
                              onChange={(e) => setAllocationForm({...allocationForm, transport_price: e.target.value})}
                              className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                              placeholder="1500.00"
                            />
                          </div>
                        </div>
                      </>
                    )}

                    {allocationForm.transport_type === 'own' && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Own Transport Price (₹) <span className="text-red-500">*</span>
                        </label>
                        <div className="relative">
                          <span className="absolute left-4 top-3 text-gray-500 font-semibold">₹</span>
                          <input
                            required
                            type="number"
                            step="0.01"
                            min="0"
                            value={allocationForm.own_transport_price}
                            onChange={(e) => setAllocationForm({...allocationForm, own_transport_price: e.target.value})}
                            className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                            placeholder="1000.00"
                          />
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          Price for using farmer's own transport
                        </p>
                      </div>
                    )}

                    {allocationForm.transport_type === 'none' && (
                      <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                        <p className="text-sm text-gray-600">
                          ℹ️ No transport needed for this allocation. Workers will arrange their own transportation.
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Summary */}
                  {/* ... inside the render ... */}

{allocationForm.mukkadam_price && (
  // 🟢 CHANGED: Dynamic background color based on total cost
  <div className={`p-6 rounded-lg border-2 transition-colors ${
    (!isPriceTbd && selectedActivity && totalCost > (selectedActivity.total_price || 0) * 1.15)
      ? 'bg-red-50 border-red-300' // Error State
      : 'bg-green-50 border-green-200' // Normal State
  }`}>
    <div className="flex justify-between items-start mb-3">
      <h3 className={`font-bold ${
        (!isPriceTbd && selectedActivity && totalCost > (selectedActivity.total_price || 0) * 1.15)
        ? 'text-red-800'
        : 'text-gray-800'
      }`}>
        Allocation Summary
      </h3>
      
      {/* 🟢 ADD THIS: Visual Warning Badge */}
      {!isPriceTbd && selectedActivity && totalCost > (selectedActivity.total_price || 0) * 1.15 && (
        <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-bold rounded flex items-center border border-red-200">
          <AlertTriangle size={12} className="mr-1" />
          Exceeds 115% Limit
        </span>
      )}
    </div>

    <div className="grid grid-cols-2 gap-4">
      <div>
        <p className="text-sm text-gray-600">Area</p>
        <p className="text-2xl font-bold text-blue-600">{allocationForm.allocated_area} acres</p>
      </div>
      <div>
        <p className="text-sm text-gray-600">Mukkadam Price</p>
        <p className={`text-2xl font-bold ${isPriceTbd ? 'text-orange-500' : 'text-indigo-600'}`}>
          {isPriceTbd ? 'To Be Decided' : `₹${parseFloat(allocationForm.mukkadam_price || '0').toLocaleString()}`}
        </p>
      </div>
      <div>
        <p className="text-sm text-gray-600">Transport Cost</p>
        <p className="text-2xl font-bold text-orange-600">
          ₹{(allocationForm.transport_type === 'provider' 
            ? parseFloat(allocationForm.transport_price || '0')
            : allocationForm.transport_type === 'own'
            ? parseFloat(allocationForm.own_transport_price || '0')
            : 0).toLocaleString()}
        </p>
      </div>
      
      {/* Total Cost Section */}
      <div className={`col-span-2 pt-3 border-t-2 ${
        (!isPriceTbd && selectedActivity && totalCost > (selectedActivity.total_price || 0) * 1.15)
        ? 'border-red-200'
        : 'border-green-300'
      }`}>
        <div className="flex justify-between items-end">
          <div>
            <p className="text-sm text-gray-600">Total Cost</p>
            <p className={`text-3xl font-bold ${
              (!isPriceTbd && selectedActivity && totalCost > (selectedActivity.total_price || 0) * 1.15)
              ? 'text-red-600'
              : 'text-green-600'
            }`}>
              ₹{totalCost.toLocaleString()}
            </p>
          </div>
          
          {/* 🟢 ADD THIS: Comparison to Limit */}
          {!isPriceTbd && selectedActivity && (
            <div className="text-right">
              <p className="text-xs text-gray-500">Max Allowed (115%)</p>
              <p className="text-sm font-semibold text-gray-700">
                ₹{((selectedActivity.total_price || 0) * 1.15).toLocaleString()}
              </p>
            </div>
          )}
        </div>

        {/* 🟢 ADD THIS: Error Message */}
        {!isPriceTbd && selectedActivity && totalCost > (selectedActivity.total_price || 0) * 1.15 && (
          <p className="text-xs font-bold text-red-600 mt-2 flex items-center">
            <AlertTriangle size={14} className="mr-1" />
            Not allowed. Please find someone better.
          </p>
        )}
      </div>
    </div>
  </div>
)}

                  {/* ✅ UPDATED: Action Buttons with dynamic text */}
                  <div className="flex space-x-3 pt-4">
                    <button
                      type="button"
                      onClick={onClose}
                      className="flex-1 px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg font-semibold hover:bg-gray-50 transition"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={allocating}
                      className={`flex-1 px-6 py-3 rounded-lg font-semibold text-white transition shadow-lg ${
                        allocating
                          ? 'bg-gray-400 cursor-not-allowed'
                          : 'bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700'
                      }`}
                    >
                      {allocating 
                        ? (editMode ? 'Updating...' : 'Allocating...') 
                        : (editMode ? 'Update Allocation' : 'Confirm Allocation')
                      }
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>

        {editingMukkadam && (
          <EditMukkadamModal
            mukkadam={editingMukkadam}
            onClose={() => setEditingMukkadam(null)}
            onSuccess={() => {
              setEditingMukkadam(null);
              // Simple reload to refresh data
              if (selectedActivity && allocationForm.work_date) {
                 // Trigger a refresh logic here
                 // For now, if you want to be safe:
                 window.location.reload();
              }
            }}
          />
        )}
      </div>
    </div>
  );
};

export default ComplexAllocationModal;


