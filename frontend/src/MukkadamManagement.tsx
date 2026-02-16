// MukkadamManagement.tsx
import React, { useState, useEffect } from 'react';
import { Plus, X, Edit2, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { API_BASE_URL } from './types/config';

interface Activity {
  id: number;
  name: string;
  rate_per_acre: number;
  productivity_per_worker: number;
}

interface Mukkadam {
  mukkadam_id: number;
  mukkadam_name: string;
  crew_size: number;
  district: string;
  taluka: string;
  village: string;
  mobile_numbers: string;
  activity_rates: Activity[];
}

const MukkadamManagement: React.FC = () => {
  const [mukkadams, setMukkadams] = useState<Mukkadam[]>([]);
  const [activities, setActivities] = useState<any[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingMukkadam, setEditingMukkadam] = useState<Mukkadam | null>(null);
  const [loading, setLoading] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    mukkadam_name: '',
    crew_size: 10,
    district: 'Nashik',
    taluka: '',
    village: '',
    mobile_numbers: ''
  });

  const [selectedActivities, setSelectedActivities] = useState<{
    activity_id: number;
    rate_per_acre: number;
    productivity_per_worker: number;
  }[]>([]);

  useEffect(() => {
    loadMukkadams();
    loadActivities();
  }, []);

  const loadMukkadams = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/mukkadams/`);
      const data = await response.json();
      setMukkadams(data);
    } catch (error) {
      toast.error('Failed to load mukkadams');
    }
  };

  const loadActivities = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/activities/`);
      const data = await response.json();
      setActivities(data);
    } catch (error) {
      toast.error('Failed to load activities');
    }
  };

  const handleAddActivity = () => {
    setSelectedActivities([
      ...selectedActivities,
      { activity_id: 0, rate_per_acre: 0, productivity_per_worker: 0.15 }
    ]);
  };

  const handleRemoveActivity = (index: number) => {
    setSelectedActivities(selectedActivities.filter((_, i) => i !== index));
  };

  const handleActivityChange = (index: number, field: string, value: any) => {
    const updated = [...selectedActivities];
    updated[index] = { ...updated[index], [field]: value };
    setSelectedActivities(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Create mukkadam
      const mukkadamResponse = await fetch(`${API_BASE_URL}/api/mukkadams/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          mukkadam_id: Date.now(), // Temporary ID
          is_permanent: true
        })
      });

      if (!mukkadamResponse.ok) throw new Error('Failed to create mukkadam');
      const mukkadam = await mukkadamResponse.json();

      // Add activity rates
      for (const activity of selectedActivities) {
        if (activity.activity_id > 0) {
          await fetch(`${API_BASE_URL}/api/mukkadams/${mukkadam.mukkadam_id}/add_activity_rate/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(activity)
          });
        }
      }

      toast.success('Mukkadam added successfully!');
      setShowAddModal(false);
      resetForm();
      loadMukkadams();
    } catch (error) {
      toast.error('Failed to add mukkadam');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (mukkadamId: number) => {
    if (!confirm('Are you sure you want to delete this mukkadam?')) return;

    try {
      await fetch(`${API_BASE_URL}/api/mukkadams/${mukkadamId}/`, {
        method: 'DELETE'
      });
      toast.success('Mukkadam deleted');
      loadMukkadams();
    } catch (error) {
      toast.error('Failed to delete mukkadam');
    }
  };

  const resetForm = () => {
    setFormData({
      mukkadam_name: '',
      crew_size: 10,
      district: 'Nashik',
      taluka: '',
      village: '',
      mobile_numbers: ''
    });
    setSelectedActivities([]);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Mukkadam Management</h1>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          <Plus size={20} />
          Add Mukkadam
        </button>
      </div>

      {/* Mukkadam List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {mukkadams.map((mukkadam) => (
          <div
            key={mukkadam.mukkadam_id}
            className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-lg transition-shadow"
          >
            {/* Header */}
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="font-semibold text-lg text-gray-900">
                  {mukkadam.mukkadam_name}
                </h3>
                <p className="text-sm text-gray-500">
                  {mukkadam.village}, {mukkadam.taluka}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleDelete(mukkadam.mukkadam_id)}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>

            {/* Crew Size */}
            <div className="mb-3 pb-3 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Crew Size</span>
                <span className="font-semibold text-blue-600">
                  {mukkadam.crew_size} workers
                </span>
              </div>
              <div className="text-sm text-gray-500 mt-1">
                📞 {mukkadam.mobile_numbers || 'N/A'}
              </div>
            </div>

            {/* Activities */}
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">
                Activities & Rates
              </h4>
              {mukkadam.activity_rates && mukkadam.activity_rates.length > 0 ? (
                <div className="space-y-2">
                  {mukkadam.activity_rates.map((activity: any) => (
                    <div
                      key={activity.id}
                      className="bg-gray-50 rounded p-2 text-sm"
                    >
                      <div className="font-medium text-gray-900">
                        {activity.activity_name}
                      </div>
                      <div className="flex justify-between text-gray-600 mt-1">
                        <span>₹{activity.rate_per_acre}/ac</span>
                        <span>{activity.productivity_per_worker} ac/w/d</span>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        Daily: {(mukkadam.crew_size * activity.productivity_per_worker).toFixed(2)} acres
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No activities added</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Add Mukkadam Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex justify-between items-center p-6 border-b border-gray-200">
              <h2 className="text-xl font-bold text-gray-900">Add New Mukkadam</h2>
              <button
                onClick={() => {
                  setShowAddModal(false);
                  resetForm();
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X size={24} />
              </button>
            </div>

            {/* Modal Body */}
            <form onSubmit={handleSubmit} className="p-6">
              {/* Basic Info */}
              <div className="space-y-4 mb-6">
                <h3 className="font-semibold text-gray-900">Basic Information</h3>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Mukkadam Name *
                  </label>
                  <input
                    type="text"
                    value={formData.mukkadam_name}
                    onChange={(e) => setFormData({ ...formData, mukkadam_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Crew Size *
                    </label>
                    <input
                      type="number"
                      value={formData.crew_size}
                      onChange={(e) => setFormData({ ...formData, crew_size: parseInt(e.target.value) })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      required
                      min="1"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Mobile Number
                    </label>
                    <input
                      type="text"
                      value={formData.mobile_numbers}
                      onChange={(e) => setFormData({ ...formData, mobile_numbers: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="9876543210"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      District
                    </label>
                    <input
                      type="text"
                      value={formData.district}
                      onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Taluka
                    </label>
                    <input
                      type="text"
                      value={formData.taluka}
                      onChange={(e) => setFormData({ ...formData, taluka: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Village
                    </label>
                    <input
                      type="text"
                      value={formData.village}
                      onChange={(e) => setFormData({ ...formData, village: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>
              </div>

              {/* Activities & Rates */}
              <div className="space-y-4 mb-6">
                <div className="flex justify-between items-center">
                  <h3 className="font-semibold text-gray-900">Activities & Rates</h3>
                  <button
                    type="button"
                    onClick={handleAddActivity}
                    className="flex items-center gap-1 text-blue-600 hover:text-blue-700 text-sm"
                  >
                    <Plus size={16} />
                    Add Activity
                  </button>
                </div>

                {selectedActivities.map((activity, index) => (
                  <div key={index} className="bg-gray-50 rounded-lg p-4 relative">
                    <button
                      type="button"
                      onClick={() => handleRemoveActivity(index)}
                      className="absolute top-2 right-2 text-red-600 hover:text-red-700"
                    >
                      <X size={16} />
                    </button>

                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Activity
                        </label>
                        <select
                          value={activity.activity_id}
                          onChange={(e) => handleActivityChange(index, 'activity_id', parseInt(e.target.value))}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          required
                        >
                          <option value={0}>Select activity</option>
                          {activities.map((act) => (
                            <option key={act.id} value={act.id}>
                              {act.name}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Rate (₹/acre)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          value={activity.rate_per_acre}
                          onChange={(e) => handleActivityChange(index, 'rate_per_acre', parseFloat(e.target.value))}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          required
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Efficiency (ac/w/d)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          value={activity.productivity_per_worker}
                          onChange={(e) => handleActivityChange(index, 'productivity_per_worker', parseFloat(e.target.value))}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          required
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Daily: {(formData.crew_size * activity.productivity_per_worker).toFixed(2)} acres
                        </p>
                      </div>
                    </div>
                  </div>
                ))}

                {selectedActivities.length === 0 && (
                  <p className="text-sm text-gray-500 text-center py-4">
                    No activities added. Click "Add Activity" to add rates.
                  </p>
                )}
              </div>

              {/* Footer */}
              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddModal(false);
                    resetForm();
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? 'Adding...' : 'Add Mukkadam'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default MukkadamManagement;