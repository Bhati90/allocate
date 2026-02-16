// ClusterActivityAdder.tsx

import React, { useState, useEffect } from 'react';
import { Plus, Save, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { API_BASE_URL } from '../types/config';

interface ClusterActivityAdderProps {
  clusterId: number;
  clusterName: string;
  onClose: () => void;
  onSuccess: () => void;
}

interface AvailableActivity {
  id: number;
  name: string;
  activity_type: string;
  default_rate_per_acre: number;
  default_gap_days: number;
}

const ClusterActivityAdder: React.FC<ClusterActivityAdderProps> = ({
  clusterId,
  clusterName,
  onClose,
  onSuccess,
}) => {
  const [availableActivities, setAvailableActivities] = useState<AvailableActivity[]>([]);
  const [selectedActivityId, setSelectedActivityId] = useState<number | null>(null);
  const [customActivityName, setCustomActivityName] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  
  const [formData, setFormData] = useState({
    farmer_rate_per_acre: 0,
    gap_days: 3,
    mukkadam_rate_per_acre: 0,
    mukkadam_productivity_per_worker: 0.150,
  });
  
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAvailableActivities();
  }, [clusterId]);

  const loadAvailableActivities = async () => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/clusters/${clusterId}/available_activities/`
      );
      const data = await res.json();
      setAvailableActivities(data.available_activities);
    } catch (error) {
      toast.error('Failed to load available activities');
    }
  };

  const handleActivitySelect = (activityId: number) => {
    setSelectedActivityId(activityId);
    const activity = availableActivities.find((a) => a.id === activityId);
    if (activity) {
      setFormData({
        ...formData,
        farmer_rate_per_acre: activity.default_rate_per_acre,
        gap_days: activity.default_gap_days,
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!useCustom && !selectedActivityId) {
      toast.error('Please select an activity');
      return;
    }

    if (useCustom && !customActivityName) {
      toast.error('Please enter activity name');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        ...(useCustom
          ? { activity_name: customActivityName }
          : { activity_id: selectedActivityId }),
        ...formData,
      };

      const res = await fetch(
        `${API_BASE_URL}/api/clusters/${clusterId}/add_activity/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }
      );

      const data = await res.json();

      if (res.ok) {
        toast.success(data.message);
        onSuccess();
        onClose();
      } else {
        toast.error(data.error || 'Failed to add activity');
      }
    } catch (error) {
      toast.error('Failed to add activity');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add Activity to {clusterName}</h2>
          <button onClick={onClose} className="modal-close">
            <X size={24} />
          </button>
        </div>
        

        <form onSubmit={handleSubmit} className="activity-form">
          <div className="form-section">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={useCustom}
                onChange={(e) => setUseCustom(e.target.checked)}
              />
              <span>Create new activity</span>
            </label>

            {!useCustom ? (
              <label className="form-label">
                Select Activity
                <select
                  className="form-input"
                  value={selectedActivityId || ''}
                  onChange={(e) => handleActivitySelect(parseInt(e.target.value))}
                  required
                >
                  <option value="">-- Select Activity --</option>
                  {availableActivities.map((activity) => (
                    <option key={activity.id} value={activity.id}>
                      {activity.name} ({activity.activity_type})
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <label className="form-label">
                Activity Name
                <input
                  type="text"
                  className="form-input"
                  value={customActivityName}
                  onChange={(e) => setCustomActivityName(e.target.value)}
                  required
                />
              </label>
            )}
          </div>

          <div className="form-section">
            <h3>Farmer Rates</h3>
            
            <label className="form-label">
              Rate per Acre (₹)
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.farmer_rate_per_acre}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    farmer_rate_per_acre: parseFloat(e.target.value),
                  })
                }
                required
              />
            </label>

            <label className="form-label">
              Gap Days
              <input
                type="number"
                className="form-input"
                value={formData.gap_days}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    gap_days: parseInt(e.target.value),
                  })
                }
                required
              />
            </label>
          </div>

          <div className="form-section">
            <h3>Mukkadam Rates</h3>
            
            <label className="form-label">
              Rate per Acre (₹)
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.mukkadam_rate_per_acre}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    mukkadam_rate_per_acre: parseFloat(e.target.value),
                  })
                }
                required
              />
            </label>

            <label className="form-label">
              Productivity (acres/worker/day)
              <input
                type="number"
                step="0.001"
                className="form-input"
                value={formData.mukkadam_productivity_per_worker}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    mukkadam_productivity_per_worker: parseFloat(e.target.value),
                  })
                }
                required
              />
            </label>
          </div>

          <div className="form-actions">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary"
              disabled={loading}
            >
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              <Plus size={16} />
              Add to Cluster
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ClusterActivityAdder;