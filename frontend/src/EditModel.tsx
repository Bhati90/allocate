import React, { useState, useEffect } from 'react';
import { X, MapPin, Truck, Calendar, Save, DollarSign, Plus, Trash2, Loader2 } from 'lucide-react';
import axios from 'axios';
import { getAuthConfig } from './utils/auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_SUPPLY;

interface EditMukkadamModalProps {
  mukkadam: any;
  onClose: () => void;
  onSuccess: () => void;
}

interface AvailabilitySlot {
  id?: string;
  teamName: string;
  status: 'Available' | 'Busy' | 'Leave';
  startDate: string;
  endDate: string;
  leaderName?: string;
  leaderMobile?: string;
}

const normalizeActivityName = (displayName: string): string => {
  const words = displayName.trim().split(/\s+/);
  if (words.length === 0) return '';
  return words[0].toLowerCase() + words.slice(1).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join('');
};

const COMMON_ACTIVITIES = [
  'Pruning', 'Pasting', '1st Dipping', '2nd Dipping', '3rd Dipping',
  'First Fail Fut Removal', 'Second Fail Fut Removal', 'Shoot Tying Strings',
  'Shoot Tying Clips', 'Bagal Bali Fut Removal', 'Bunch Thinning',
  'Finger Thinning', 'Berry Thinning', 'Bunch Selection', 'Bunch Tying',
  'Bunch Variation', 'Shenda Topping', 'Paper Wrapping', 'Paper Removal',
  'April Pruning', 'Harvesting', 'New Plantation',
];

const EditMukkadamModal: React.FC<EditMukkadamModalProps> = ({
  mukkadam,
  onClose,
  onSuccess
}) => {
  
  const [loadingData, setLoadingData] = useState(true);
  const [saving, setSaving] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    current_latitude: '',
    current_longitude: '',
    transport_mode: 'no_vehicle',
    transport_charges: {
      bikeBeyondKm: '', bikeChargePerBike: '', pickupChargeDetails: '', currentlyStationedAt: ''
    },
    rate_card: { other: '' } as Record<string, string>,
  });

  const [availabilityList, setAvailabilityList] = useState<AvailabilitySlot[]>([]);
  
  const [newSlot, setNewSlot] = useState<AvailabilitySlot>({
    teamName: 'Main Crew',
    status: 'Available',
    startDate: '',
    endDate: '',
    leaderName: '',
    leaderMobile: ''
  });

  // ✅ FETCH FRESH DATA ON MOUNT
  useEffect(() => {
    const fetchFullDetails = async () => {
      try {
        setLoadingData(true);
        // Fetch the specific mukkadam details to ensure we have ALL availability/rates
        // (The list view might only have a summary)
        const response = await axios.get(
            `${API_BASE_URL}/api/mukkadam/${mukkadam.id}/`, 
            getAuthConfig() // Ensure auth headers are passed
        );
        
        const data = response.data;

        // 1. Setup Rate Card
        const rateCard: Record<string, string> = { other: '' };
        if (data.rate_card) {
          Object.entries(data.rate_card).forEach(([key, value]) => {
            rateCard[key] = String(value || '');
          });
        }

        // 2. Setup Availability
        const availabilities = (data.team_availabilities || []).map((s: any, i: number) => ({
          id: s.id || `fetched-${i}`,
          teamName: s.teamName || s.teamNumber || 'Main Crew',
          status: s.status || 'Available',
          startDate: s.startDate,
          endDate: s.endDate,
          leaderName: s.leaderName || '',
          leaderMobile: s.leaderMobile || ''
        }));

        // 3. Update State
        setFormData({
          current_latitude: data.current_latitude || '',
          current_longitude: data.current_longitude || '',
          transport_mode: data.transport_mode || 'no_vehicle',
          transport_charges: data.transport_charges || {
            bikeBeyondKm: '', bikeChargePerBike: '', pickupChargeDetails: '', currentlyStationedAt: ''
          },
          rate_card: rateCard,
        });
        
        setAvailabilityList(availabilities);

      } catch (error) {
        console.error("Failed to fetch mukkadam details", error);
        alert("Could not load latest data. Please close and try again.");
      } finally {
        setLoadingData(false);
      }
    };

    fetchFullDetails();
  }, [mukkadam.id]);


  // --- Handlers ---

  const handleRateCardChange = (displayName: string, value: string) => {
    const normalizedKey = displayName === 'Other' ? 'other' : normalizeActivityName(displayName);
    setFormData(prev => ({
      ...prev,
      rate_card: { ...prev.rate_card, [normalizedKey]: value }
    }));
  };

  // Helper to safely add/subtract days without timezone issues
  const addDays = (dateStr: string, days: number) => {
    const date = new Date(dateStr);
    date.setUTCDate(date.getUTCDate() + days); // Force UTC to keep YYYY-MM-DD consistent
    return date.toISOString().split('T')[0];
  };

const addAvailabilitySlot = () => {
    if (!newSlot.startDate || !newSlot.endDate) {
      alert("Please select Start and End dates");
      return;
    }

    const start = newSlot.startDate;
    const end = newSlot.endDate;

    // 1. Find if this new range falls INSIDE an existing 'Available' slot
    const targetIndex = availabilityList.findIndex(slot => 
      slot.status === 'Available' && 
      slot.startDate <= start && 
      slot.endDate >= end
    );

    if (targetIndex !== -1) {
      // ✅ OVERLAP FOUND: We need to SPLIT the existing slot
      const original = availabilityList[targetIndex];
      const newSlots: AvailabilitySlot[] = [];

      // A. Create "Before" Segment (if gap exists)
      if (original.startDate < start) {
        newSlots.push({
          ...original,
          id: `split-${Date.now()}-1`,
          endDate: addDays(start, -1) // End date is day before leave starts
        });
      }

      // B. Create the "New" Segment (The Leave/Busy slot)
      newSlots.push({ 
        ...newSlot, 
        id: `new-${Date.now()}` 
      });

      // C. Create "After" Segment (if gap exists)
      if (original.endDate > end) {
        newSlots.push({
          ...original,
          id: `split-${Date.now()}-2`,
          startDate: addDays(end, 1) // Start date is day after leave ends
        });
      }

      // Replace the single original slot with the new split segments
      const updatedList = [...availabilityList];
      updatedList.splice(targetIndex, 1, ...newSlots);
      setAvailabilityList(updatedList);

    } else {
      // ⚠️ No direct overlap containment found. 
      // Just add it to the list (standard behavior)
      setAvailabilityList([...availabilityList, { ...newSlot, id: `new-${Date.now()}` }]);
    }

    // Reset Form
    setNewSlot({
      teamName: 'Main Crew', 
      status: 'Available', 
      startDate: '', 
      endDate: '', 
      leaderName: '', 
      leaderMobile: ''
    });
  };

  const removeAvailabilitySlot = (index: number) => {
    if(!window.confirm("Remove this availability slot?")) return;
    const updated = [...availabilityList];
    updated.splice(index, 1);
    setAvailabilityList(updated);
  };

  

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setSaving(true);

    try {
      const payload = {
        current_latitude: formData.current_latitude,
        current_longitude: formData.current_longitude,
        transport_mode: formData.transport_mode,
        transport_charges: formData.transport_charges,
        rate_card: formData.rate_card,
        team_availabilities: availabilityList 
      };

      const config = getAuthConfig();

      await axios.patch(
        `${API_BASE_URL}/api/mukkadam/${mukkadam.id}/`,
        payload,
        config
      );

      alert('✅ Mukkadam updated successfully!');
      onSuccess();
      onClose();
    } catch (error: any) {
      console.error('Update error:', error);
      alert('Failed to update: ' + (error.response?.data?.error || error.message));
    } finally {
      setSaving(false);
    }
  };

  const getStatusColor = (status: string) => {
    if (status === 'Busy') return 'bg-red-100 text-red-800 border-red-200';
    if (status === 'Leave') return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    return 'bg-green-100 text-green-800 border-green-200';
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[60] p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-y-auto">
        
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
          <div>
            <h2 className="text-xl font-bold text-white">Edit Mukkadam Details</h2>
            <p className="text-white text-sm opacity-90">{mukkadam.mukkadam_name} • {mukkadam.village}</p>
          </div>
          <button onClick={onClose} className="text-white hover:bg-white hover:bg-opacity-20 p-2 rounded-full transition">
            <X size={20} />
          </button>
        </div>

        {loadingData ? (
          <div className="flex flex-col items-center justify-center h-64">
            <Loader2 className="animate-spin text-purple-600 mb-2" size={32} />
            <p className="text-gray-500">Loading full details...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 space-y-8">
            
            {/* 1. RATE CARD */}
            <div className="space-y-4">
              <h3 className="font-bold text-gray-900 flex items-center border-b-2 border-green-200 pb-2">
                <DollarSign className="mr-2 text-green-600" size={20} /> Rate Card (₹ per acre)
              </h3>
              <div className="bg-yellow-50 p-3 rounded-lg border-2 border-yellow-300 mb-3">
                <label className="block text-xs font-bold text-gray-900 mb-1">Other (Base Price)</label>
                <div className="relative">
                  <span className="absolute left-3 top-2 text-gray-500 font-semibold text-sm">₹</span>
                  <input
                    type="number" step="0.01" min="0"
                    value={formData.rate_card.other}
                    onChange={(e) => handleRateCardChange('Other', e.target.value)}
                    className="w-full pl-6 pr-4 py-1.5 border border-yellow-400 rounded font-semibold text-sm"
                    placeholder="5000"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {COMMON_ACTIVITIES.map((activity) => {
                  const normalizedKey = normalizeActivityName(activity);
                  return (
                    <div key={activity} className="bg-white border border-gray-200 rounded p-2">
                      <label className="block text-[10px] font-medium text-gray-700 mb-1 truncate" title={activity}>{activity}</label>
                      <div className="relative">
                        <span className="absolute left-1.5 top-1 text-gray-400 text-[10px]">₹</span>
                        <input
                          type="number" step="0.01" min="0"
                          value={formData.rate_card[normalizedKey] || ''}
                          onChange={(e) => handleRateCardChange(activity, e.target.value)}
                          className="w-full pl-4 pr-1 py-1 border border-gray-300 rounded text-xs"
                          placeholder={formData.rate_card.other || '0'}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 2. TRANSPORT & LOCATION (Combined Row) */}
            <div className="grid md:grid-cols-2 gap-6">
              {/* Location */}
              <div className="space-y-4">
                <h3 className="font-bold text-gray-900 flex items-center border-b-2 border-purple-200 pb-2">
                  <MapPin className="mr-2 text-purple-600" size={20} /> Current Location
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-600">Latitude</label>
                    <input
                      type="number" step="0.000001"
                      value={formData.current_latitude}
                      onChange={(e) => setFormData({...formData, current_latitude: e.target.value})}
                      className="w-full p-2 border border-gray-300 rounded text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600">Longitude</label>
                    <input
                      type="number" step="0.000001"
                      value={formData.current_longitude}
                      onChange={(e) => setFormData({...formData, current_longitude: e.target.value})}
                      className="w-full p-2 border border-gray-300 rounded text-sm"
                    />
                  </div>
                </div>
              </div>

              {/* Transport */}
              <div className="space-y-4">
                <h3 className="font-bold text-gray-900 flex items-center border-b-2 border-cyan-200 pb-2">
                  <Truck className="mr-2 text-cyan-600" size={20} /> Transport
                </h3>
                <select
                  value={formData.transport_mode}
                  onChange={(e) => setFormData({...formData, transport_mode: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded text-sm mb-2"
                >
                  <option value="no_vehicle">No Vehicle</option>
                  <option value="bike">Bike</option>
                  <option value="pickup">Pickup</option>
                </select>
                
                {/* Dynamic Transport Inputs */}
                {formData.transport_mode === 'bike' && (
                  <div className="grid grid-cols-2 gap-2">
                    <input type="number" placeholder="Free KM" className="p-2 border rounded text-sm"
                      value={formData.transport_charges.bikeBeyondKm}
                      onChange={e => setFormData({...formData, transport_charges: {...formData.transport_charges, bikeBeyondKm: e.target.value}})} />
                    <input type="number" placeholder="Charge/KM" className="p-2 border rounded text-sm"
                      value={formData.transport_charges.bikeChargePerBike}
                      onChange={e => setFormData({...formData, transport_charges: {...formData.transport_charges, bikeChargePerBike: e.target.value}})} />
                  </div>
                )}
                {formData.transport_mode === 'pickup' && (
                   <input type="text" placeholder="Charge (e.g. 20/km)" className="w-full p-2 border rounded text-sm"
                   value={formData.transport_charges.pickupChargeDetails}
                   onChange={e => setFormData({...formData, transport_charges: {...formData.transport_charges, pickupChargeDetails: e.target.value}})} />
                )}
              </div>
            </div>

            {/* 3. AVAILABILITY (New Section) */}
            <div className="space-y-4">
              <h3 className="font-bold text-gray-900 flex items-center border-b-2 border-blue-200 pb-2">
                <Calendar className="mr-2 text-blue-600" size={20} /> Availability & Schedule
              </h3>

              {/* List Existing */}
              <div className="space-y-2 max-h-40 overflow-y-auto bg-gray-50 p-2 rounded-lg">
                {availabilityList.length === 0 && <p className="text-xs text-gray-400 italic text-center">No custom availability set</p>}
                {availabilityList.map((slot, idx) => (
                  <div key={idx} className={`flex justify-between items-center p-2 rounded border-l-4 bg-white shadow-sm ${getStatusColor(slot.status)}`}>
                    <div className="text-xs">
                      <span className="font-bold">{slot.startDate}</span> to <span className="font-bold">{slot.endDate}</span>
                      <span className="mx-2">•</span>
                      <span className="uppercase font-semibold">{slot.status}</span>
                      <span className="ml-2 text-gray-500">({slot.teamName})</span>
                    </div>
                    <button type="button" onClick={() => removeAvailabilitySlot(idx)} className="text-red-400 hover:text-red-600">
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>

              {/* Add New */}
              <div className="bg-blue-50 p-3 rounded-lg border border-blue-100">
                <p className="text-xs font-bold text-blue-800 mb-2">Add New Period</p>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                  <input type="date" className="p-1.5 border rounded text-xs" 
                    value={newSlot.startDate} onChange={e => setNewSlot({...newSlot, startDate: e.target.value})} />
                  <input type="date" className="p-1.5 border rounded text-xs" 
                    value={newSlot.endDate} onChange={e => setNewSlot({...newSlot, endDate: e.target.value})} />
                  <select className="p-1.5 border rounded text-xs" 
                    value={newSlot.status} onChange={e => setNewSlot({...newSlot, status: e.target.value as any})}>
                    <option value="Available">Available</option>
                    <option value="Busy">Busy</option>
                    <option value="Leave">On Leave</option>
                  </select>
                  <input type="text" placeholder="Team Name" className="p-1.5 border rounded text-xs" 
                    value={newSlot.teamName} onChange={e => setNewSlot({...newSlot, teamName: e.target.value})} />
                  <button type="button" onClick={addAvailabilitySlot} 
                    className="bg-blue-600 text-white rounded text-xs font-bold hover:bg-blue-700 flex items-center justify-center">
                    <Plus size={14} className="mr-1"/> Add
                  </button>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex space-x-3 pt-4 border-t">
              <button type="button" onClick={onClose} className="flex-1 px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg font-semibold hover:bg-gray-50">
                Cancel
              </button>
              <button type="submit" disabled={saving} className={`flex-1 px-6 py-3 rounded-lg font-semibold text-white transition flex items-center justify-center gap-2 ${saving ? 'bg-gray-400 cursor-not-allowed' : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700'}`}>
                {saving ? (
                  <>
                    <Loader2 className="animate-spin" size={18} /> Saving...
                  </>
                ) : (
                  <>
                    <Save size={18} /> Save All Changes
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default EditMukkadamModal;