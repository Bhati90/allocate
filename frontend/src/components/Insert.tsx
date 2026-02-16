// components/InsertActivityModal.tsx
import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { API_BASE_URL } from '../types/config';
import { toast } from 'react-hot-toast';

interface Activity {
  id: number;
  name: string;
  phase_order: number;
  gap_days: number;
}

interface InsertActivityModalProps {
  clusterId: number;
  onClose: () => void;
  onSuccess: () => void;
}

const InsertActivityModal: React.FC<InsertActivityModalProps> = ({
  clusterId,
  onClose,
  onSuccess,
}) => {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(false);
  
  const [formData, setFormData] = useState({
    name: '',
    activity_type: '',
    default_rate_per_acre: '',
    insert_after_activity_id: '',
    gap_days_from_previous: '',
    mukkadam_rate_per_acre: '',
    mukkadam_productivity_per_worker: '0.150',
    is_strict: false,
    estimated_workers_per_acre: '10',
  });

  // Load existing activities
  useEffect(() => {
    loadActivities();
  }, []);

  const loadActivities = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/activities/`);
      const data = await response.json();
      
      // Sort by some order if available
      setActivities(data);
    } catch (error) {
      toast.error('Failed to load activities');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name || !formData.insert_after_activity_id || !formData.gap_days_from_previous) {
      toast.error('Please fill in all required fields');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/activities/insert_between/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name,
          activity_type: formData.activity_type,
          default_rate_per_acre: parseFloat(formData.default_rate_per_acre),
          insert_after_activity_id: parseInt(formData.insert_after_activity_id),
          gap_days_from_previous: parseInt(formData.gap_days_from_previous),
          mukkadam_rate_per_acre: parseFloat(formData.mukkadam_rate_per_acre || '0'),
          mukkadam_productivity_per_worker: parseFloat(formData.mukkadam_productivity_per_worker),
          is_strict: formData.is_strict,
          estimated_workers_per_acre: parseInt(formData.estimated_workers_per_acre),
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        toast.error(result.error || 'Failed to insert activity');
        return;
      }

      toast.success(result.message);
      onSuccess();
      onClose();
    } catch (error) {
      toast.error('Failed to insert activity');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const selectedActivity = activities.find(
    a => a.id === parseInt(formData.insert_after_activity_id)
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Insert New Activity</h3>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Activity Name */}
            <div className="form-group">
              <label className="form-label">Activity Name *</label>
              <input
                type="text"
                className="form-input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Fertilizer Application"
                required
              />
            </div>

            {/* Activity Type */}
            <div className="form-group">
              <label className="form-label">Activity Type</label>
              <input
                type="text"
                className="form-input"
                value={formData.activity_type}
                onChange={(e) => setFormData({ ...formData, activity_type: e.target.value })}
                placeholder="e.g., fertilization, pruning"
              />
            </div>

            {/* Insert After Which Activity */}
            <div className="form-group">
              <label className="form-label">Insert After *</label>
              <select
                className="form-select"
                value={formData.insert_after_activity_id}
                onChange={(e) => setFormData({ ...formData, insert_after_activity_id: e.target.value })}
                required
              >
                <option value="">Select activity to insert after</option>
                {activities.map((activity) => (
                  <option key={activity.id} value={activity.id}>
                    {activity.name}
                  </option>
                ))}
              </select>
              <small className="form-help">
                New activity will be inserted after this one in the lifecycle
              </small>
            </div>

            {/* Gap Days from Previous */}
            <div className="form-group">
              <label className="form-label">Days After Previous Activity *</label>
              <input
                type="number"
                className="form-input"
                value={formData.gap_days_from_previous}
                onChange={(e) => setFormData({ ...formData, gap_days_from_previous: e.target.value })}
                placeholder="e.g., 5"
                min="1"
                required
              />
              {selectedActivity && (
                <small className="form-help" style={{ color: '#10b981' }}>
                  Will occur {formData.gap_days_from_previous || '?'} days after {selectedActivity.name}
                </small>
              )}
            </div>

            <hr style={{ margin: '1.5rem 0', border: 'none', borderTop: '1px solid #e5e7eb' }} />

            {/* Farmer Rate */}
            <div className="form-group">
              <label className="form-label">Farmer Rate (₹/acre) *</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.default_rate_per_acre}
                onChange={(e) => setFormData({ ...formData, default_rate_per_acre: e.target.value })}
                placeholder="e.g., 1000"
                required
              />
            </div>

            {/* Mukkadam Rate */}
            <div className="form-group">
              <label className="form-label">Mukkadam Rate (₹/acre)</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.mukkadam_rate_per_acre}
                onChange={(e) => setFormData({ ...formData, mukkadam_rate_per_acre: e.target.value })}
                placeholder="e.g., 800"
              />
              <small className="form-help">
                Leave blank to use 80% of farmer rate as default
              </small>
            </div>

            {/* Productivity */}
            <div className="form-group">
              <label className="form-label">Mukkadam Productivity (acres/worker/day)</label>
              <input
                type="number"
                step="0.001"
                className="form-input"
                value={formData.mukkadam_productivity_per_worker}
                onChange={(e) => setFormData({ ...formData, mukkadam_productivity_per_worker: e.target.value })}
                placeholder="e.g., 0.150"
              />
            </div>

            <hr style={{ margin: '1.5rem 0', border: 'none', borderTop: '1px solid #e5e7eb' }} />

            {/* Estimated Workers */}
            <div className="form-group">
              <label className="form-label">Estimated Workers per Acre</label>
              <input
                type="number"
                className="form-input"
                value={formData.estimated_workers_per_acre}
                onChange={(e) => setFormData({ ...formData, estimated_workers_per_acre: e.target.value })}
                placeholder="e.g., 10"
              />
            </div>

            {/* Is Strict */}
            <div className="form-group">
              <label className="form-checkbox">
                <input
                  type="checkbox"
                  checked={formData.is_strict}
                  onChange={(e) => setFormData({ ...formData, is_strict: e.target.checked })}
                />
                <span>Strict Activity (must be completed on exact date)</span>
              </label>
            </div>

            {/* Preview */}
            {selectedActivity && formData.gap_days_from_previous && (
              <div style={{
                padding: '1rem',
                backgroundColor: '#f0f9ff',
                borderRadius: '8px',
                marginTop: '1rem'
              }}>
                <strong>📅 Timeline Preview:</strong>
                <div style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
                  ... → {selectedActivity.name} (Day X) → 
                  <strong style={{ color: '#0284c7' }}> {formData.name || 'New Activity'} (Day X + {formData.gap_days_from_previous})</strong> → 
                  Next Activity ...
                </div>
              </div>
            )}
          </div>

          <div className="modal-footer">
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
              {loading ? 'Inserting...' : 'Insert Activity'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default InsertActivityModal;