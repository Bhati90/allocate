import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Users, Truck, X, Calendar, MapPin, TrendingUp,
  CheckCircle, AlertCircle, ArrowRight, Layers
} from 'lucide-react';
import { getAuthConfig } from './utils/auth';

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
  onSuccess: () => void;
  mukkadams: Mukkadam[];
  transportProviders: TransportProvider[];
}


const ComplexAllocationModal: React.FC<ComplexAllocationModalProps> = ({
  job,
  onClose,
  onSuccess,
  mukkadams,
  transportProviders
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

  // Calculate auto-price when area changes
  useEffect(() => {
    if (selectedActivity && allocationForm.allocated_area) {
      const area = parseFloat(allocationForm.allocated_area);
      if (!isNaN(area) && area > 0) {
        const price = area * selectedActivity.rate_per_acre;
        setAllocationForm(prev => ({
          ...prev,
          mukkadam_price: price.toFixed(2)
        }));
      }
    }
  }, [allocationForm.allocated_area, selectedActivity]);

  // Calculate crew capacity when mukkadam is selected
  // Calculate crew capacity when mukkadam is selected OR crew_size changes
useEffect(() => {
  if (allocationForm.mukkadam_id && selectedActivity) {
    const mukkadam = mukkadams.find(m => m.id === parseInt(allocationForm.mukkadam_id));
    if (mukkadam) {
      // Use custom crew size if provided, otherwise use mukkadam's default
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

      // Auto-fill area if empty
      if (!allocationForm.allocated_area) {
        const suggestedArea = Math.min(maxAreaPerDay, selectedActivity.remaining_area);
        setAllocationForm(prev => ({
          ...prev,
          allocated_area: suggestedArea.toFixed(2)
        }));
      }
    }
  }
}, [allocationForm.mukkadam_id, allocationForm.crew_size, selectedActivity]); // ✅ ADD crew_size dependency
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

  const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  if (!selectedActivity) return;

  // Validation
  if (!allocationForm.mukkadam_id) {
    alert('Please select a mukkadam');
    return;
  }
  if (!allocationForm.allocated_area || parseFloat(allocationForm.allocated_area) <= 0) {
    alert('Please enter valid area');
    return;
  }
  if (parseFloat(allocationForm.allocated_area) > selectedActivity.remaining_area) {
    alert(`Cannot allocate more than ${selectedActivity.remaining_area} acres`);
    return;
  }
  if (allocationForm.transport_type === 'provider' && !allocationForm.transport_provider_id) {
    alert('Please select transport provider');
    return;
  }
  if (allocationForm.transport_type === 'own' && !allocationForm.own_transport_price) {
    alert('Please enter own transport price');
    return;
  }
  if (allocationForm.transport_type === 'provider' && !allocationForm.transport_price) {
    alert('Please enter transport price');
    return;
  }

  setAllocating(true);

  try {
    let notes = `Activity ID: ${selectedActivity.activity_id}`;
    if (allocationForm.crew_size) {
      notes += `\nCrew Size: ${allocationForm.crew_size} workers`;
    }

    const payload = {
      // Activity reference
      activity_id: selectedActivity.activity_id,  // External API activity ID
      job_id: job.work_id,  // Job ID for finding/creating activity
      
      // Activity details (for auto-creation)
      activity_name: selectedActivity.activity_name,
      activity_type: selectedActivity.activity_type,
      scheduled_datetime: selectedActivity.scheduled_date,
      total_area: selectedActivity.total_area,
      total_price: selectedActivity.total_price,
      location: selectedActivity.location,
      estimated_workers: selectedActivity.estimated_workers,
      rate_per_acre: selectedActivity.rate_per_acre,
      
      // Allocation details
      mukkadam_id: parseInt(allocationForm.mukkadam_id),
      allocated_area: parseFloat(allocationForm.allocated_area),
      work_date: allocationForm.work_date,
      crew_size: allocationForm.crew_size ? parseInt(allocationForm.crew_size) : null,
      mukkadam_price: parseFloat(allocationForm.mukkadam_price),
      
      // Transport
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
    const response = await axios.post(`${API_BASE_URL_A}/ap/allocations/`, payload, config);

    alert(`✅ Allocated ${allocationForm.allocated_area} acres successfully!\n${response.data.message || ''}`);
    

    onSuccess();
    
    // Reset form but keep activity selected
    setAllocationForm({
      mukkadam_id: '',
      allocated_area: '',
      work_date: selectedActivity.scheduled_date,
      mukkadam_price: '',
      crew_size: '', // ✅ RESET THIS TOO
      transport_type: 'provider',
      transport_provider_id: '',
      own_transport_price: '',
      transport_price: ''
    });
    setCrewCapacity(null);

  }catch (error: any) {
    console.error('Allocation error:', error);
    alert('Failed to allocate: ' + (error.response?.data?.error || error.message));
  } finally {
    setAllocating(false);
  }
};

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
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-blue-600 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
        <div>
          <h2 className="text-2xl font-bold text-white">Allocate Complex Job</h2>
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
        {/* ✅ ADD FARMER DETAILS SECTION AT TOP */}
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
              
              {/* ✅ JOB FINANCIAL SUMMARY */}
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
            
            <div className="space-y-3">
              {job.activities?.map((activity) => (
                <button
                  key={activity.id}
                  onClick={() => handleActivitySelect(activity)}
                  className={`w-full text-left p-4 rounded-lg border-2 transition ${
                    selectedActivity?.id === activity.id
                      ? 'border-blue-500 bg-blue-50'
                      : activity.is_fully_allocated
                      ? 'border-green-300 bg-green-50'
                      : 'border-gray-200 bg-white hover:border-blue-300'
                  }`}
                  disabled={activity.is_fully_allocated}
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
                    <div className="flex items-center">
                      <MapPin size={12} className="mr-1" />
                      {activity.location}
                    </div>
                    <div className="flex items-center">
                      <Calendar size={12} className="mr-1" />
                      {new Date(activity.scheduled_date).toLocaleDateString()}
                    </div>
                    <div className="flex items-center">
                      <TrendingUp size={12} className="mr-1" />
                      {activity.allocated_area}/{activity.total_area} acres
                    </div>
                    {/* ✅ ADD REVENUE INFO */}
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
                
                {/* ✅ ENHANCED Activity Info with Financial Details */}
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

                  {/* ✅ EXPECTED COSTS FROM API */}
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
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-gray-900 flex items-center border-b-2 border-indigo-200 pb-2">
                      <Users className="mr-2 text-indigo-500" /> Mukkadam & Area
                    </h3>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Select Mukkadam <span className="text-red-500">*</span>
                      </label>
                      <select
                        required
                        value={allocationForm.mukkadam_id}
                        onChange={(e) => setAllocationForm({...allocationForm, mukkadam_id: e.target.value})}
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">-- Select Mukkadam --</option>
                        {mukkadams.map(m => (
                          <option key={m.id} value={m.id}>
                            {m.mukkadam_name} - {m.village} (Crew: {m.crew_size})
                          </option>
                        ))}
                      </select>

                      {/* AFTER the Mukkadam dropdown, ADD THIS: */}

{selectedMukkadam && (
  <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-200">
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

{/* ✅ ADD THIS NEW SECTION */}
{selectedMukkadam && (
  <div>
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
                          max={selectedActivity.remaining_area}
                          value={allocationForm.allocated_area}
                          onChange={(e) => setAllocationForm({...allocationForm, allocated_area: e.target.value})}
                          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                          placeholder="5.00"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Max: {selectedActivity.remaining_area.toFixed(2)} acres
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
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Mukkadam Price (₹) <span className="text-red-500">*</span>
                      </label>
                      <div className="relative">
                        <span className="absolute left-4 top-3 text-gray-500 font-semibold">₹</span>
                        <input
                          required
                          type="number"
                          step="0.01"
                          min="0"
                          value={allocationForm.mukkadam_price}
                          onChange={(e) => setAllocationForm({...allocationForm, mukkadam_price: e.target.value})}
                          className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                          placeholder="Auto-calculated"
                        />
                      </div>
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
                          <select
                            required
                            value={allocationForm.transport_provider_id}
                            onChange={(e) => setAllocationForm({...allocationForm, transport_provider_id: e.target.value})}
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                          >
                            <option value="">-- Select Transport Provider --</option>
                            {transportProviders.map(t => (
                              <option key={t.id} value={t.id}>
                                {t.name} - {t.base_location} (Max: {t.max_distance}km)
                              </option>
                            ))}
                          </select>
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
                  {allocationForm.mukkadam_price && (
                    <div className="bg-green-50 p-6 rounded-lg border-2 border-green-200">
                      <h3 className="font-bold text-gray-800 mb-3">Allocation Summary</h3>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-sm text-gray-600">Area</p>
                          <p className="text-2xl font-bold text-blue-600">{allocationForm.allocated_area} acres</p>
                        </div>
                        <div>
                          <p className="text-sm text-gray-600">Mukkadam Price</p>
                          <p className="text-2xl font-bold text-indigo-600">₹{parseFloat(allocationForm.mukkadam_price).toLocaleString()}</p>
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
                        <div className="col-span-2 pt-3 border-t-2 border-green-300">
                          <p className="text-sm text-gray-600">Total Cost</p>
                          <p className="text-3xl font-bold text-green-600">
                            ₹{totalCost.toLocaleString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Action Buttons */}
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
                      {allocating ? 'Allocating...' : 'Confirm Allocation'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ComplexAllocationModal;