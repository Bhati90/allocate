// ClusterCalendar.tsx - Add Mukkadam Rate Editing

import React, { useState, useEffect } from 'react';
import { X, Save, Edit2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { API_BASE_URL } from './types/config';
import './Cluster.css';

interface ClusterActivityCalendarProps {
  clusterId: number;
  clusterName: string;
  onClose: () => void;
}

interface Mukkadam {
  mukkadam_id: number;
  mukkadam_name: string;
  crew_size: number;
  village: string;
  taluka: string;
}

interface MukkadamActivityRate {
  id: number;
  activity_id: number;
  activity_name: string;
  rate_per_acre: number;
  productivity_per_worker: number;
  is_active: boolean;
}
// ClusterCalendar.tsx - Simplified without mukkadam selector

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

const ClusterActivityCalendar: React.FC<ClusterActivityCalendarProps> = ({
  clusterId,
  clusterName,
  onClose,
}) => {
  const [activities, setActivities] = useState<ActivityCalendarItem[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Farmer editing states
  const [editingFarmerActivityId, setEditingFarmerActivityId] = useState<number | null>(null);
  const [editFarmerValues, setEditFarmerValues] = useState<{
    rate_per_acre: number;
    gap_days: number;
  }>({ rate_per_acre: 0, gap_days: 0 });

  // Mukkadam editing states
  const [editingMukkadamActivityId, setEditingMukkadamActivityId] = useState<number | null>(null);
  const [editMukkadamValues, setEditMukkadamValues] = useState<{
    rate_per_acre: number;
    productivity_per_worker: number;
  }>({ rate_per_acre: 0, productivity_per_worker: 0 });

  const [activeTab, setActiveTab] = useState<'farmer' | 'mukkadam'>('farmer');

  useEffect(() => {
    loadActivities();
  }, [clusterId]);

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

  // Farmer handlers (existing)
  const handleFarmerEditStart = (activity: ActivityCalendarItem) => {
    setEditingFarmerActivityId(activity.activity_id);
    setEditFarmerValues({
      rate_per_acre: activity.rate_per_acre,
      gap_days: activity.gap_days,
    });
  };

  const handleFarmerEditCancel = () => {
    setEditingFarmerActivityId(null);
  };

  const handleSaveFarmerEdit = async () => {
    if (!editingFarmerActivityId) return;

    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/clusters/${clusterId}/activity-calendar/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            rate_overrides: [
              {
                activity_id: editingFarmerActivityId,
                rate_per_acre: editFarmerValues.rate_per_acre,
              },
            ],
            gap_overrides: [
              {
                activity_id: editingFarmerActivityId,
                gap_days: editFarmerValues.gap_days,
              },
            ],
          }),
        }
      );

      if (res.ok) {
        toast.success('Farmer rates updated!');
        setEditingFarmerActivityId(null);
        loadActivities();
      } else {
        toast.error('Failed to update');
      }
    } catch (error) {
      toast.error('Failed to update');
    } finally {
      setLoading(false);
    }
  };

  // Mukkadam handlers (NEW)
  const handleMukkadamEditStart = (activity: ActivityCalendarItem) => {
    setEditingMukkadamActivityId(activity.activity_id);
    setEditMukkadamValues({
      rate_per_acre: activity.mukkadam_rate_per_acre,
      productivity_per_worker: activity.mukkadam_productivity,
    });
  };

  const handleMukkadamEditCancel = () => {
    setEditingMukkadamActivityId(null);
  };

  const handleSaveMukkadamEdit = async () => {
    if (!editingMukkadamActivityId) return;

    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/clusters/${clusterId}/activity-calendar/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mukkadam_rate_overrides: [
              {
                activity_id: editingMukkadamActivityId,
                rate_per_acre: editMukkadamValues.rate_per_acre,
                productivity_per_worker: editMukkadamValues.productivity_per_worker,
              },
            ],
          }),
        }
      );

      if (res.ok) {
        toast.success('Mukkadam rates updated!');
        setEditingMukkadamActivityId(null);
        loadActivities();
      } else {
        toast.error('Failed to update');
      }
    } catch (error) {
      toast.error('Failed to update');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="calendar-modal-overlay" onClick={onClose}>
      <div className="calendar-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="calendar-modal-header">
          <h2>{clusterName} - Activity Calendar & Rates</h2>
          <button onClick={onClose} className="modal-close">
            <X size={24} />
          </button>
        </div>

        {/* Tabs */}
        <div className="calendar-tabs">
          <button
            className={`calendar-tab ${activeTab === 'farmer' ? 'active' : ''}`}
            onClick={() => setActiveTab('farmer')}
          >
            Farmer Rates & Schedule
          </button>
          <button
            className={`calendar-tab ${activeTab === 'mukkadam' ? 'active' : ''}`}
            onClick={() => setActiveTab('mukkadam')}
          >
            Mukkadam Default Rates
          </button>
        </div>

        <div className="calendar-modal-body">
          {/* Farmer Tab */}
          {activeTab === 'farmer' && (
            <div className="activities-table-wrapper">
              <p className="tab-description">
                Set default rates and scheduling gaps for farmers in this cluster
              </p>
              <table className="activities-table">
                <thead>
                  <tr>
                    
                    <th>Activity</th>
                    <th>Rate (₹/acre)</th>
                    <th>Gap (days)</th>
                    {/* <th>Strict</th> */}
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {activities.map((activity) => {
                    const isEditing = editingFarmerActivityId === activity.activity_id;

                    return (
                      <tr key={activity.activity_id}>
                        {/* <td>{activity.phase_order}</td> */}
                        <td>
                          <strong>{activity.activity_name}</strong>
                          <div className="activity-type">{activity.activity_type}</div>
                        </td>
                        <td>
                          {isEditing ? (
                            <input
                              type="number"
                              step="0.01"
                              value={editFarmerValues.rate_per_acre}
                              onChange={(e) =>
                                setEditFarmerValues({
                                  ...editFarmerValues,
                                  rate_per_acre: parseFloat(e.target.value),
                                })
                              }
                              className="edit-input"
                            />
                          ) : (
                            <>
                              ₹{activity.rate_per_acre}
                              {activity.rate_overridden && (
                                <span className="override-badge">Custom</span>
                              )}
                            </>
                          )}
                        </td>
                        <td>
                          {isEditing ? (
                            <input
                              type="number"
                              value={editFarmerValues.gap_days}
                              onChange={(e) =>
                                setEditFarmerValues({
                                  ...editFarmerValues,
                                  gap_days: parseInt(e.target.value),
                                })
                              }
                              className="edit-input"
                            />
                          ) : (
                            <>
                              {activity.gap_days} days
                              {activity.gap_overridden && (
                                <span className="override-badge">Custom</span>
                              )}
                            </>
                          )}
                        </td>
                        {/* <td>{activity.is_strict ? '✓' : '—'}</td> */}
                        <td>
                          {isEditing ? (
                            <div className="action-buttons">
                              <button
                                onClick={handleSaveFarmerEdit}
                                className="btn-icon success"
                                disabled={loading}
                              >
                                <Save size={16} />
                              </button>
                              <button
                                onClick={handleFarmerEditCancel}
                                className="btn-icon"
                              >
                                <X size={16} />
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => handleFarmerEditStart(activity)}
                              className="btn-icon"
                            >
                              <Edit2 size={16} />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Mukkadam Tab */}
          {activeTab === 'mukkadam' && (
            <div className="activities-table-wrapper">
              <p className="tab-description">
                Set default rates and efficiency for mukkadams in this cluster. These will be used when creating new mukkadams.
              </p>
              <table className="activities-table">
                <thead>
                  <tr>
                    {/* <th>Order</th> */}
                    <th>Activity</th>
                    <th>Rate (₹/acre)</th>
                    <th>Efficiency (ac/w/d)</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {activities.map((activity) => {
                    const isEditing = editingMukkadamActivityId === activity.activity_id;

                    return (
                      <tr key={activity.activity_id}>
                        {/* <td>{activity.phase_order}</td> */}
                        <td>
                          <strong>{activity.activity_name}</strong>
                          <div className="activity-type">{activity.activity_type}</div>
                        </td>
                        <td>
                          {isEditing ? (
                            <input
                              type="number"
                              step="0.01"
                              value={editMukkadamValues.rate_per_acre}
                              onChange={(e) =>
                                setEditMukkadamValues({
                                  ...editMukkadamValues,
                                  rate_per_acre: parseFloat(e.target.value),
                                })
                              }
                              className="edit-input"
                            />
                          ) : (
                            <>
                              ₹{activity.mukkadam_rate_per_acre}
                              {activity.mukkadam_rate_overridden && (
                                <span className="override-badge">Custom</span>
                              )}
                            </>
                          )}
                        </td>
                        <td>
                          {isEditing ? (
                            <input
                              type="number"
                              step="0.001"
                              value={editMukkadamValues.productivity_per_worker}
                              onChange={(e) =>
                                setEditMukkadamValues({
                                  ...editMukkadamValues,
                                  productivity_per_worker: parseFloat(e.target.value),
                                })
                              }
                              className="edit-input"
                            />
                          ) : (
                            activity.mukkadam_productivity.toFixed(3)
                          )}
                        </td>
                        <td>
                          {isEditing ? (
                            <div className="action-buttons">
                              <button
                                onClick={handleSaveMukkadamEdit}
                                className="btn-icon success"
                                disabled={loading}
                              >
                                <Save size={16} />
                              </button>
                              <button
                                onClick={handleMukkadamEditCancel}
                                className="btn-icon"
                              >
                                <X size={16} />
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => handleMukkadamEditStart(activity)}
                              className="btn-icon"
                            >
                              <Edit2 size={16} />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ClusterActivityCalendar;