// GlobalActivityManager.tsx

import React, { useState } from 'react';
import { Plus, Save, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { API_BASE_URL } from '../types/config';
import './Global.css';
import InsertActivityModal from './Insert';

interface GlobalActivityManagerProps {
  onClose: () => void;
  onSuccess: () => void;
  clusterId: number;
}


interface ActivityCalendarItem {
  activity_id: number;
  activity_name: string;
  activity_type: string;
  // Farmer rates
  rate_per_acre: number;
  rate_overridden: boolean;
  gap_days: number;
  gap_overridden: boolean;
  // Mukkadam rates
  mukkadam_rate_per_acre: number;
  mukkadam_productivity: number;
  mukkadam_rate_overridden: boolean;
  // Common
  is_strict: boolean;
  phase_order: number;
}

const GlobalActivityManager: React.FC<GlobalActivityManagerProps> = ({
  onClose,
  onSuccess,
  clusterId,
}) => {


const [showInsertActivityModal, setShowInsertActivityModal] = useState(false);
  const [activities, setActivities] = useState<ActivityCalendarItem[]>([]);
  const loadActivities = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/clusters/${clusterId}/activity-calendar/`
      );
      const data = await res.json();
      setActivities(data.activities || []);
    } catch (error) {
      toast.error('Failed to load activities');
    } finally {
      setLoading(false);
    }
  };
  const [formData, setFormData] = useState({
    name: '',
    activity_type: '',
    default_rate_per_acre: 0,
    default_gap_days: 3,
    mukkadam_rate_per_acre: 0,
    mukkadam_productivity_per_worker: 0.150,
    is_strict: false,
    estimated_workers_per_acre: 10,
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name) {
      toast.error('Activity name is required');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/activities/create_global_activity/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData),
        }
      );

      const data = await res.json();

      if (res.ok) {
        toast.success(data.message);
        onSuccess();
        onClose();
      } else {
        toast.error(data.error || 'Failed to create activity');
      }
    } catch (error) {
      toast.error('Failed to create activity');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create Global Activity</h2>
          <button onClick={onClose} className="modal-close">
            <X size={24} />
          </button>
        </div>
{/* <button
  className="btn-primary"
  onClick={() => setShowInsertActivityModal(true)}
>
  + Insert Activity Between
</button> */}
        

        <form onSubmit={handleSubmit} className="activity-form">
          <div className="form-section">
            <h3>Basic Information</h3>
            
            <label className="form-label">
              Activity Name *
              <input
                type="text"
                className="form-input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </label>

            <label className="form-label">
              Activity Type
              <input
                type="text"
                className="form-input"
                placeholder="e.g., pruning, harvesting"
                value={formData.activity_type}
                onChange={(e) =>
                  setFormData({ ...formData, activity_type: e.target.value })
                }
              />
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.is_strict}
                onChange={(e) =>
                  setFormData({ ...formData, is_strict: e.target.checked })
                }
              />
              <span>Strict Activity (must be completed on scheduled date)</span>
            </label>
          </div>

          <div className="form-section">
            <h3>Farmer Defaults</h3>
            
            <label className="form-label">
              Rate per Acre (₹)
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.default_rate_per_acre}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    default_rate_per_acre: parseFloat(e.target.value),
                  })
                }
              />
            </label>

            <label className="form-label">
              Gap Days (scheduling)
              <input
                type="number"
                className="form-input"
                value={formData.default_gap_days}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    default_gap_days: parseInt(e.target.value),
                  })
                }
              />
            </label>
          </div>

          <div className="form-section">
            <h3>Mukkadam Defaults</h3>
            
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
              />
            </label>

            <label className="form-label">
              Estimated Workers per Acre
              <input
                type="number"
                className="form-input"
                value={formData.estimated_workers_per_acre}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    estimated_workers_per_acre: parseInt(e.target.value),
                  })
                }
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
            <button
              type="submit"
              className="btn-primary"
              disabled={loading}
            >
              <Save size={16} />
              Create Activity
            </button>
          </div>
        </form>

        {showInsertActivityModal && (
  <InsertActivityModal
    clusterId={clusterId}
    onClose={() => setShowInsertActivityModal(false)}
    onSuccess={() => {
      // Refresh your activities list
      loadActivities();
    }}
  />
)}
      </div>
    </div>
  );
};

export default GlobalActivityManager;