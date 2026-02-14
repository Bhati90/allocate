// components/MukkadamPanel.tsx
import React, { useState } from 'react';
import { Plus, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { Mukkadam, Allocation } from '../types/types';
import './job.css';
import { API_BASE_URL } from '@/types/config';

interface MukkadamPanelProps {
  mukkadams: Mukkadam[];
  selectedDate: Date;
  allocations: Allocation[];
  loading: boolean;
  onRefresh: () => void;
  onMukkadamClick?: (m: Mukkadam) => void;
  onAddDayCrew?: (m: Mukkadam, date: Date) => void;
  clusterId: number;  
}

// Standard rates - hardcoded, no API calls needed
const STANDARD_RATES = [
  {
    activity_id: 1,
    activity_name: 'Paper Wrapping',
    rate_per_acre: 1000,
    productivity_per_worker: 0.15,
  },
  {
    activity_id: 3,
    activity_name: 'Harvesting',
    rate_per_acre: 1500,
    productivity_per_worker: 0.10,
  },
  {
    activity_id: 5,
    activity_name: 'First Dipping',
    rate_per_acre: 1200,
    productivity_per_worker: 0.12,
  },
  {
    activity_id: 7,
    activity_name: 'Pruning',
    rate_per_acre: 800,
    productivity_per_worker: 0.20,
  },
  {
    activity_id: 9,
    activity_name: 'Weeding',
    rate_per_acre: 600,
    productivity_per_worker: 0.25,
  },
  {
    activity_id: 11,
    activity_name: 'Fertilizing',
    rate_per_acre: 700,
    productivity_per_worker: 0.18,
  },
  {
    activity_id: 13,
    activity_name: 'Pest Control',
    rate_per_acre: 900,
    productivity_per_worker: 0.16,
  },
];

const MukkadamPanel: React.FC<MukkadamPanelProps> = ({
  mukkadams,
  selectedDate,
  allocations,
  loading,
  onRefresh,
  onMukkadamClick,
  onAddDayCrew,
  clusterId
}) => {
  const getMukkadamCapacity = (mukkadam: Mukkadam) => {
    const total =
      (mukkadam as any).available_crew_size ?? mukkadam.crew_size;

    const mukkadamAllocs = allocations.filter(
      (a) => a.mukkadam === mukkadam.mukkadam_id,
    );
    const usedWorkers = mukkadamAllocs.reduce(
      (sum, a) => sum + a.allocated_workers,
      0,
    );
    const remaining = total - usedWorkers;
    const percentage = total > 0 ? (usedWorkers / total) * 100 : 0;

    return { total, used: usedWorkers, remaining, percentage };
  };

  const getCapacityColor = (percentage: number) => {
    if (percentage >= 100) return 'danger';
    if (percentage >= 70) return 'warning';
    return 'good';
  };

  // -------- Add Mukkadam modal state --------
  const [showAddModal, setShowAddModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activities, setActivities] = useState<any[]>([]);
  const [formData, setFormData] = useState({
    mukkadam_name: '',
    crew_size: 10,
    district: 'Nashik',
    taluka: '',
    village: '',
    mobile_numbers: '',
  });
const [selectedActivities, setSelectedActivities] = useState<{
  activity_id: number;
  rate_per_acre: number;
  productivity_per_worker: number;
}[]>([]);

  const loadActivities = async () => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/activities/`,
      );
      const data = await res.json();
      setActivities(data);
    } catch (error) {
      toast.error('Failed to load activities');
    }
  };
const [searchText, setSearchText] = useState('');
const visibleMukkadams = mukkadams.filter(m =>
  m.mukkadam_name.toLowerCase().includes(searchText.toLowerCase())
);

  const handleAddActivityRow = () => {
    setSelectedActivities((prev) => [
      ...prev,
      { activity_id: 0, rate_per_acre: 0, productivity_per_worker: 0.15 },
    ]);
  };

  const handleRemoveActivityRow = (index: number) => {
    setSelectedActivities((prev) => prev.filter((_, i) => i !== index));
  };

  const handleActivityChange = (
    index: number,
    field: 'activity_id' | 'rate_per_acre' | 'productivity_per_worker',
    value: number,
  ) => {
    setSelectedActivities((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  const resetForm = () => {
    setFormData({
      mukkadam_name: '',
      crew_size: 10,
      district: 'Nashik',
      taluka: '',
      village: '',
      mobile_numbers: '',
    });
    setSelectedActivities([]);
  };

  const handleCreateMukkadam = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      // create mukkadam
      const mukkadamRes = await fetch(
        'http://localhost:8001/tender/api/mukkadams/',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...formData,
            mukkadam_id: Date.now(),
            is_permanent: true,
            cluster: clusterId,  
          }),
        },
      );
      if (!mukkadamRes.ok) throw new Error('Failed to create mukkadam');
      const mukkadam = await mukkadamRes.json();

      // add activity rates
      for (const a of selectedActivities) {
        if (a.activity_id > 0) {
          await fetch(
            `http://localhost:8001/tender/api/mukkadams/${mukkadam.mukkadam_id}/add_activity_rate/`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(a),
            },
          );
        }
      }

      toast.success('Mukkadam added successfully!');
      setShowAddModal(false);
      resetForm();
      onRefresh();
    } catch (err) {
      toast.error('Failed to add mukkadam');
    } finally {
      setSaving(false);
    }
  };

  // -------- UI --------
  return (
    <div className="mukkadam-panel">
      <div className="panel-header">
        <h2 className="panel-title">Mukkadams</h2>
        <div className="panel-actions">
  <input
    type="text"
    className="form-input mukkadam-search"
    placeholder="Search mukkadam..."
    value={searchText}
    onChange={e => setSearchText(e.target.value)}
  />

<button
  type="button"
  className="btn-primary btn-sm"
  onClick={async () => {
    await loadActivities();
    
    // ✅ Load cluster mukkadam rates (not farmer rates)
    try {
      const res = await fetch(
        `http://localhost:8001/tender/api/clusters/${clusterId}/activity-calendar/`
      );
      const data = await res.json();
      
      // ✅ Pre-fill with cluster MUKKADAM rates and efficiency
      setSelectedActivities(
        data.activities.map((act: any) => ({
          activity_id: act.activity_id,
          rate_per_acre: act.mukkadam_rate_per_acre,  // ✅ Changed from rate_per_acre
          productivity_per_worker: act.mukkadam_productivity  // ✅ Changed from 0.150
        }))
      );
    } catch (error) {
      // Fallback to standard rates if API fails
      setSelectedActivities(
        STANDARD_RATES.map(rate => ({
          activity_id: rate.activity_id,
          rate_per_acre: rate.rate_per_acre,
          productivity_per_worker: rate.productivity_per_worker,
        }))
      );
    }
    
    setShowAddModal(true);
  }}
>
  <Plus size={14} /> Add
</button>
</div>

      </div>

      <div className="mukkadam-panel-content">
        <div className="selected-date-info">
          <strong>Selected Date:</strong>
          <div>
            {selectedDate.toLocaleDateString('en-US', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
          </div>
        </div>

        {loading ? (
          <div className="empty-state">
            <div className="loading-spinner"></div>
            <p>Loading mukkadams...</p>
          </div>
        ) : mukkadams.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👥</div>
            <p className="empty-state-text">No mukkadams available</p>
          </div>
        ) : (
          <div className="mukkadams-list">


{visibleMukkadams.map((mukkadam) => {
  const capacity = getMukkadamCapacity(mukkadam);
  const mukkadamAllocs = allocations.filter(
    (a) => a.mukkadam === mukkadam.mukkadam_id,
  );

  // ✅ Group allocations by activity with proper number conversion
  const activitySummary = mukkadamAllocs.reduce((acc, alloc) => {
    const key = alloc.activity_name;
    if (!acc[key]) {
      acc[key] = {
        activity_name: key,
        total_area: 0,
        total_workers: 0,
        count: 0
      };
    }
    // ✅ Convert to number explicitly before adding
    acc[key].total_area += Number(alloc.allocated_area) || 0;
    acc[key].total_workers += Number(alloc.allocated_workers) || 0;
    acc[key].count += 1;
    return acc;
  }, {} as Record<string, { activity_name: string; total_area: number; total_workers: number; count: number }>);

  const summaries = Object.values(activitySummary);

  return (
    <div
      key={mukkadam.mukkadam_id}
      className="mukkadam-card"
      onClick={() => onMukkadamClick && onMukkadamClick(mukkadam)}
    >
      <div className="mukkadam-header">
        <div className="mukkadam-name">
          {mukkadam.mukkadam_name}
        </div>
        <div className="crew-badge">
          {capacity.remaining}/{capacity.total} workers
        </div>

        <button
          className="btn-tertiary add-day-crew-btn"
          onClick={(e) => {
            e.stopPropagation();
            onAddDayCrew && onAddDayCrew(mukkadam, selectedDate);
          }}
        >
          + Add
        </button>
      </div>

      <div className="capacity-bar-container">
        <div className="capacity-label">
          <span>Capacity</span>
          <span>{capacity.percentage.toFixed(0)}%</span>
        </div>
        <div className="capacity-bar">
          <div
            className={`capacity-fill ${getCapacityColor(capacity.percentage)}`}
            style={{ width: `${Math.min(capacity.percentage, 100)}%` }}
          />
        </div>
      </div>

      {/* ✅ Show summarized allocations with explicit number conversion */}
      {summaries.length > 0 && (
        <div className="mukkadam-allocations">
          {summaries.map((summary) => (
            <div key={summary.activity_name} className="allocation-summary">
              {summary.activity_name}: {Number(summary.total_area).toFixed(2)}ac
              ({summary.total_workers}w, {summary.count}x)
            </div>
          ))}
        </div>
      )}

      <div className="mukkadam-info">
        <small>
          📍 {mukkadam.village}, {mukkadam.taluka}
        </small>
      </div>
    </div>
  );
})}
          </div>
        )}
      </div>

      {/* Add Mukkadam Modal */}
      
        {showAddModal && (
  <div className="mukkadam-modal-overlay">
    <div className="mukkadam-modal">
            <div className="flex justify-between items-center p-6 border-b border-gray-200">
              <h2 className="text-xl font-bold text-gray-900">
                Add New Mukkadam
              </h2>
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

            <form onSubmit={handleCreateMukkadam} className="p-6">
              {/* Basic Information */}
              <div className="space-y-4 mb-6">
                <h3 className="font-semibold text-gray-900">
                  Basic Information
                </h3>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Mukkadam Name *
                  </label>
                  <input
                    type="text"
                    value={formData.mukkadam_name}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        mukkadam_name: e.target.value,
                      })
                    }
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
                      min={1}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          crew_size: parseInt(e.target.value || '0', 10),
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Mobile Number
                    </label>
                    <input
    type="tel"
    inputMode="numeric"
    pattern="[0-9]{10}"
    maxLength={10}
    value={formData.mobile_numbers}
    onChange={(e) => {
      const value = e.target.value.replace(/\D/g, ""); // remove non-digits

      if (value.length <= 10) {
        setFormData({
          ...formData,
          mobile_numbers: value,
        });
      }
    }}
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
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          district: e.target.value,
                        })
                      }
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
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          taluka: e.target.value,
                        })
                      }
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
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          village: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>
              </div>

              {/* Activities & Rates */}
              <div className="space-y-4 mb-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="font-semibold text-gray-900">
                      Activities & Rates
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                      Pre-filled with standard rates. Edit as needed or add more.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddActivityRow}
                    className="flex items-center gap-1 text-blue-600 hover:text-blue-700 text-sm"
                  >
                    <Plus size={16} />
                    Add Activity
                  </button>
                </div>

                {selectedActivities.map((activity, index) => {
                  const isStandard = STANDARD_RATES.some(sr => sr.activity_id === activity.activity_id);
                  
                  return (
                    <div
                      key={index}
                      className="rounded-lg p-4 relative border-l-4"
                      style={{
                        backgroundColor: '#f9fafb',
                        borderLeftColor: isStandard ? '#22c55e' : '#3b82f6'
                      }}
                    >
                      {isStandard && (
                        <div className="absolute top-2 left-2">
                          <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded font-medium">
                            ✓ Standard Rate
                          </span>
                        </div>
                      )}
                      
                      <button
                        type="button"
                        onClick={() => handleRemoveActivityRow(index)}
                        className="absolute top-2 right-2 text-red-600 hover:text-red-700"
                      >
                        <X size={16} />
                      </button>

                      <div className="grid grid-cols-3 gap-4" style={{ marginTop: isStandard ? '1.5rem' : '0' }}>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Activity
                          </label>
                          <select
                            value={activity.activity_id}
                            onChange={(e) =>
                              handleActivityChange(
                                index,
                                'activity_id',
                                parseInt(e.target.value || '0', 10),
                              )
                            }
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
                            onChange={(e) =>
                              handleActivityChange(
                                index,
                                'rate_per_acre',
                                parseFloat(e.target.value || '0'),
                              )
                            }
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
                            step="0.001"
                            value={activity.productivity_per_worker}
                            onChange={(e) =>
                              handleActivityChange(
                                index,
                                'productivity_per_worker',
                                parseFloat(e.target.value || '0'),
                              )
                            }
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            required
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            Daily capacity:{' '}
                            {(
                              formData.crew_size *
                              activity.productivity_per_worker
                            ).toFixed(2)}{' '}
                            acres
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}

                {selectedActivities.length === 0 && (
                  <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
                    <p className="text-sm text-gray-500 mb-3">
                      No activities added yet
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedActivities(
                          STANDARD_RATES.map(rate => ({
                            activity_id: rate.activity_id,
                            rate_per_acre: rate.rate_per_acre,
                            productivity_per_worker: rate.productivity_per_worker,
                          }))
                        );
                        toast.success('Standard rates loaded!');
                      }}
                      className="text-sm text-blue-600 hover:text-blue-700 font-medium underline"
                    >
                      Load Standard Rates
                    </button>
                  </div>
                )}
              </div>

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
                  disabled={saving}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? 'Adding...' : 'Add Mukkadam'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default MukkadamPanel;