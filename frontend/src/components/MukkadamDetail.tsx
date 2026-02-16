// components/MukkadamDetailPanel.tsx
import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Save, X, Edit2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { Mukkadam } from '../types/types';

import './detail.css'
import { API_BASE_URL } from '@/types/config';

interface Props {
  mukkadam: Mukkadam | null;
  onRefresh: () => void;
}

const MukkadamDetailPanel: React.FC<Props> = ({ mukkadam, onRefresh }) => {
  const [activities, setActivities] = useState<any[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingActivity, setEditingActivity] = useState<number | null>(null);
  const [editValues, setEditValues] = useState<any>({});

  // ✅ NEW: State for editing mukkadam details
  const [editingMukkadam, setEditingMukkadam] = useState(false);
  const [mukkadamEditValues, setMukkadamEditValues] = useState({
    mukkadam_name: '',
    crew_size: 0,
    mobile_numbers: '',
    village: '',
    taluka: '',
    district: ''
  });

  // Form for adding new activity
  const [newActivity, setNewActivity] = useState({
    activity_id: 0,
    rate_per_acre: 0,
    productivity_per_worker: 0.15
  });

  useEffect(() => {
    loadActivities();
  }, []);

  // ✅ NEW: Initialize mukkadam edit values when mukkadam changes
  useEffect(() => {
    if (mukkadam) {
      setMukkadamEditValues({
        mukkadam_name: mukkadam.mukkadam_name,
        crew_size: mukkadam.crew_size,
        mobile_numbers: mukkadam.mobile_numbers || '',
        village: mukkadam.village || '',
        taluka: mukkadam.taluka || '',
        district: mukkadam.district || ''
      });
    }
  }, [mukkadam]);

  const loadActivities = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/activities/`);
      const data = await response.json();
      setActivities(data);
    } catch (error) {
      console.error('Failed to load activities');
    }
  };

  // ✅ NEW: Handle mukkadam details edit
  const handleEditMukkadamStart = () => {
    setEditingMukkadam(true);
  };

  const handleEditMukkadamCancel = () => {
    setEditingMukkadam(false);
    if (mukkadam) {
      setMukkadamEditValues({
        mukkadam_name: mukkadam.mukkadam_name,
        crew_size: mukkadam.crew_size,
        mobile_numbers: mukkadam.mobile_numbers || '',
        village: mukkadam.village || '',
        taluka: mukkadam.taluka || '',
        district: mukkadam.district || ''
      });
    }
  };

  const handleEditMukkadamSave = async () => {
    if (!mukkadam) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/mukkadams/${mukkadam.mukkadam_id}/`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(mukkadamEditValues)
        }
      );

      if (response.ok) {
        toast.success('Mukkadam details updated!');
        setEditingMukkadam(false);
        onRefresh();
      } else {
        const error = await response.json();
        toast.error(error.error || 'Failed to update');
      }
    } catch (error) {
      toast.error('Failed to update');
      console.error(error);
    }
  };

  const handleEditStart = (activityRate: any) => {
    setEditingActivity(activityRate.id);
    setEditValues({
      rate_per_acre: activityRate.rate_per_acre,
      productivity_per_worker: activityRate.productivity_per_worker
    });
  };

  const handleEditCancel = () => {
    setEditingActivity(null);
    setEditValues({});
  };

  const handleEditSave = async (activityRateId: number) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/mukkadam-rates/${activityRateId}/`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(editValues)
        }
      );

      if (response.ok) {
        toast.success('Updated successfully!');
        setEditingActivity(null);
        setEditValues({});
        onRefresh();
      } else {
        toast.error('Failed to update');
      }
    } catch (error) {
      console.error(error);
    }
  };

  const handleDeleteActivity = async (activityRateId: number) => {
    if (!confirm('Delete this activity rate?')) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/mukkadam-rates/${activityRateId}/`,
        { method: 'DELETE' }
      );

      if (response.ok) {
        toast.success('Deleted!');
        onRefresh();
      } else {
        toast.error('Failed to delete');
      }
    } catch (error) {
      toast.error('Failed to delete');
      console.error(error);
    }
  };

  const handleAddActivity = async () => {
    if (!mukkadam || newActivity.activity_id === 0) {
      toast.error('Please select an activity');
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/mukkadams/${mukkadam.mukkadam_id}/add_activity_rate/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newActivity)
        }
      );

      if (response.ok) {
        toast.success('Activity added!');
        setShowAddModal(false);
        setNewActivity({ activity_id: 0, rate_per_acre: 0, productivity_per_worker: 0.15 });
        onRefresh();
      } else {
        toast.error('Failed to add activity');
      }
    } catch (error) {
      toast.error('Failed to add activity');
      console.error(error);
    }
  };

  if (!mukkadam) {
    return (
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Mukkadam Details</h2>
        </div>
        <div className="panel-content">
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <p className="empty-state-text">Select a mukkadam to see details</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      {/* Header */}
      <div className="panel-header">
        <h2 className="panel-title">{mukkadam.mukkadam_name}</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {/* ✅ NEW: Edit button for mukkadam details */}
          {editingMukkadam ? (
            <>
              <button
                className="btn-success"
                onClick={handleEditMukkadamSave}
                title="Save"
              >
                <Save size={16} />
              </button>
              <button
                className="btn-secondary"
                onClick={handleEditMukkadamCancel}
                title="Cancel"
              >
                <X size={16} />
              </button>
            </>
          ) : (
            <button
              className="btn-secondary"
              onClick={handleEditMukkadamStart}
              title="Edit Details"
            >
              <Edit2 size={16} />
            </button>
          )}
          <button
            className="btn-secondary"
            onClick={() => setShowAddModal(true)}
            title="Add Activity"
          >
            <Plus size={16} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="panel-content">
        {/* ✅ UPDATED: Basic Info with Edit Mode */}
        <div className="mukkadam-detail-info">
          {/* Name */}
          {editingMukkadam ? (
            <div className="info-row">
              <span className="info-label">Name:</span>
              <input
                type="text"
                value={mukkadamEditValues.mukkadam_name}
                onChange={(e) =>
                  setMukkadamEditValues({
                    ...mukkadamEditValues,
                    mukkadam_name: e.target.value
                  })
                }
                className="form-input"
                style={{ flex: 1 }}
              />
            </div>
          ) : null}

          {/* Crew Size */}
          <div className="info-row">
            <span className="info-label">Crew Size:</span>
            {editingMukkadam ? (
              <input
                type="number"
                value={mukkadamEditValues.crew_size}
                onChange={(e) =>
                  setMukkadamEditValues({
                    ...mukkadamEditValues,
                    crew_size: parseInt(e.target.value) || 0
                  })
                }
                className="form-input"
                style={{ flex: 1 }}
              />
            ) : (
              <span className="info-value">
                {(mukkadam as any).available_crew_size ?? mukkadam.crew_size} workers
              </span>
            )}
          </div>

          {/* Mobile */}
          <div className="info-row">
            <span className="info-label">Mobile:</span>
            {editingMukkadam ? (
              <input
                type="text"
                value={mukkadamEditValues.mobile_numbers}
                onChange={(e) =>
                  setMukkadamEditValues({
                    ...mukkadamEditValues,
                    mobile_numbers: e.target.value
                  })
                }
                className="form-input"
                placeholder="Phone numbers"
                style={{ flex: 1 }}
              />
            ) : (
              <span className="info-value">
                {mukkadam.mobile_numbers ? `📞 ${mukkadam.mobile_numbers}` : 'Not set'}
              </span>
            )}
          </div>

          {/* Village */}
          <div className="info-row">
            <span className="info-label">Village:</span>
            {editingMukkadam ? (
              <input
                type="text"
                value={mukkadamEditValues.village}
                onChange={(e) =>
                  setMukkadamEditValues({
                    ...mukkadamEditValues,
                    village: e.target.value
                  })
                }
                className="form-input"
                placeholder="Village"
                style={{ flex: 1 }}
              />
            ) : (
              <span className="info-value">{mukkadam.village || 'Not set'}</span>
            )}
          </div>

          {/* Taluka */}
          <div className="info-row">
            <span className="info-label">Taluka:</span>
            {editingMukkadam ? (
              <input
                type="text"
                value={mukkadamEditValues.taluka}
                onChange={(e) =>
                  setMukkadamEditValues({
                    ...mukkadamEditValues,
                    taluka: e.target.value
                  })
                }
                className="form-input"
                placeholder="Taluka"
                style={{ flex: 1 }}
              />
            ) : (
              <span className="info-value">{mukkadam.taluka || 'Not set'}</span>
            )}
          </div>

          {/* District */}
          <div className="info-row">
            <span className="info-label">District:</span>
            {editingMukkadam ? (
              <input
                type="text"
                value={mukkadamEditValues.district}
                onChange={(e) =>
                  setMukkadamEditValues({
                    ...mukkadamEditValues,
                    district: e.target.value
                  })
                }
                className="form-input"
                placeholder="District"
                style={{ flex: 1 }}
              />
            ) : (
              <span className="info-value">{mukkadam.district || 'Not set'}</span>
            )}
          </div>

          {/* Full Location (only in view mode) */}
          {!editingMukkadam && mukkadam.village && (
            <div className="info-row">
              <span className="info-label">Location:</span>
              <span className="info-value">
                📍 {mukkadam.village}, {mukkadam.taluka}, {mukkadam.district}
              </span>
            </div>
          )}
        </div>

        {/* Activities & Rates */}
        <div className="activities-section">
          <h3 className="section-title">Activities & Rates</h3>

          {mukkadam.activity_rates && mukkadam.activity_rates.length > 0 ? (
            <div className="activities-list">
              {mukkadam.activity_rates.map((activityRate: any) => {
                const isEditing = editingActivity === activityRate.id;
                const effectiveCrew =
                  (mukkadam as any).available_crew_size ?? mukkadam.crew_size;

                const dailyCapacity = effectiveCrew *
                  (isEditing ? editValues.productivity_per_worker : activityRate.productivity_per_worker);

                return (
                  <div key={activityRate.id} className="activity-rate-card">
                    <div className="activity-rate-header">
                      <span className="activity-name">
                        {activityRate.activity_name}
                      </span>
                      <div className="activity-actions">
                        {isEditing ? (
                          <>
                            <button
                              onClick={() => handleEditSave(activityRate.id)}
                              className="icon-btn success"
                              title="Save"
                            >
                              <Save size={14} />
                            </button>
                            <button
                              onClick={handleEditCancel}
                              className="icon-btn"
                              title="Cancel"
                            >
                              <X size={14} />
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => handleEditStart(activityRate)}
                              className="icon-btn"
                              title="Edit"
                            >
                              <Edit2 size={14} />
                            </button>
                            <button
                              onClick={() => handleDeleteActivity(activityRate.id)}
                              className="icon-btn danger"
                              title="Delete"
                            >
                              <Trash2 size={14} />
                            </button>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="activity-rate-details">
                      <div className="detail-item">
                        <label>Rate (₹/acre)</label>
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.01"
                            value={editValues.rate_per_acre}
                            onChange={(e) =>
                              setEditValues({
                                ...editValues,
                                rate_per_acre: parseFloat(e.target.value)
                              })
                            }
                            className="edit-input"
                          />
                        ) : (
                          <span className="detail-value">₹{activityRate.rate_per_acre}</span>
                        )}
                      </div>

                      <div className="detail-item">
                        <label>Efficiency (ac/w/d)</label>
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.01"
                            value={editValues.productivity_per_worker}
                            onChange={(e) =>
                              setEditValues({
                                ...editValues,
                                productivity_per_worker: parseFloat(e.target.value)
                              })
                            }
                            className="edit-input"
                          />
                        ) : (
                          <span className="detail-value">
                            {activityRate.productivity_per_worker}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="daily-capacity">
                      Daily Capacity: <strong>{dailyCapacity.toFixed(2)} acres</strong>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="empty-text">No activities added yet</p>
          )}
        </div>
      </div>

      {/* Add Activity Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Add Activity Rate</h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="modal-close"
              >
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Activity</label>
                <select
                  value={newActivity.activity_id}
                  onChange={(e) =>
                    setNewActivity({
                      ...newActivity,
                      activity_id: parseInt(e.target.value)
                    })
                  }
                  className="form-select"
                >
                  <option value={0}>Select activity</option>
                  {activities.map((act) => (
                    <option key={act.id} value={act.id}>
                      {act.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Rate (₹/acre)</label>
                <input
                  type="number"
                  step="0.01"
                  value={newActivity.rate_per_acre}
                  onChange={(e) =>
                    setNewActivity({
                      ...newActivity,
                      rate_per_acre: parseFloat(e.target.value)
                    })
                  }
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Efficiency (acres/worker/day)</label>
                <input
                  type="number"
                  step="0.01"
                  value={newActivity.productivity_per_worker}
                  onChange={(e) =>
                    setNewActivity({
                      ...newActivity,
                      productivity_per_worker: parseFloat(e.target.value)
                    })
                  }
                  className="form-input"
                />
                <span className="form-hint">
                  Daily capacity:{' '}
                  {(((mukkadam as any).available_crew_size ?? mukkadam.crew_size) *
                    newActivity.productivity_per_worker
                  ).toFixed(2)} acres
                </span>
              </div>
            </div>

            <div className="modal-footer">
              <button
                onClick={() => setShowAddModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button onClick={handleAddActivity} className="btn-primary">
                Add Activity
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MukkadamDetailPanel;