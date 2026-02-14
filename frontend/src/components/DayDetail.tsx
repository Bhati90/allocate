// components/DayDetailModal.tsx
import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { Allocation, Job, Mukkadam } from '../types/types';
import './Day.css';
import { Tractor, User, AlertCircle } from 'lucide-react';
import { useState } from 'react';
// import { toast } from './ui/sonner';
import { toast } from './ui/sonner';
import { API_BASE_URL } from '@/types/config';
type PotentialStatus = 'PARTIAL' | 'NONE';

interface CalendarFilters {
  farmerId: string | null;
  mukkadamId: number | null;
  dateFrom: string | null;
  dateTo: string | null;
  plotId: number | null;          // ✅ ADD
  activityId: number | null;      // ✅ ADD
  cropName: string | null;        // ✅ ADD
  variety: string | null;         // ✅ ADD
}
interface PotentialJob {
  date: string;          // suggested potential date (same logic as JobDetailPanel)
  activityId: number;
  activityName: string;
  status: PotentialStatus;
  cropName: string;
  variety: string;
  bookedArea: number;
  unbookedArea: number;
  bookedRate: number;
  clusterRate: number;
  farmerId: string;
  farmerName: string;
  plotId: number;
  potentialRevenue: number;
  plotName: string;
  jobId: string;
}


interface DayDetailModalProps {
  date: Date;
  allocations: Allocation[];
  mukkadams: Mukkadam[];
  capacitySummary: {
    used: number;
    total: number;
    percentage: number;
    conflicts: any[];
    mukkadamsOnLeave: number;
  };
   potentialJobs?: PotentialJob[];
  overloads: any[];    
  jobs: Job[];
  leaves: any[];
  filters?: CalendarFilters;  // ✅ ADD THIS
  allJobs?: Job[]; 
  onClose: () => void;
  onAllocationDateChange: (allocation: Allocation) => void;
  onAllocationDelete: (allocation: Allocation) => void;
  onStartAllocation: (jobId: string, activityId: number, activity: any) => void;
  clusterId: number; // ✅ ADD THIS - to look up job details
}

const DayDetailModal: React.FC<DayDetailModalProps> = ({
  date,
  allocations,
  mukkadams,
  overloads,
  filters,
  allJobs,
  capacitySummary,
  leaves,potentialJobs,
  onClose,
onAllocationDateChange,
  onAllocationDelete,
  jobs,onStartAllocation,clusterId
}) => {
  const [activeTab, setActiveTab] = useState<'allocations' | 'jobs' | 'conflicts' |  'potential'>('allocations');

  const dateStr = date.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  });

  const isoDate = date.toLocaleDateString('en-CA'); 

  const jobsOnThisDay = jobs.filter(job =>
    job.activities?.some(act => act.scheduled_date === isoDate)
  );

  // ✅ Filter allocations based on activity filter
const filteredAllocations = allocations.filter(alloc => {
  // If no activity filter, show all
  if (!filters?.activityId) return true;

  // ✅ Use allJobs instead of jobs for lookup
  const job = (allJobs || jobs).find(j => j.job_id === alloc.job_id);
  if (!job) return true; // Keep if we can't find job

  // Find the activity for this allocation
  const activity = job.activities?.find(a => a.id === alloc.job_activity);
  if (!activity) return true;

  // Check if activity matches filter
  return activity.activity_id === filters.activityId;
});



// Add to DayDetailModal state
const [showEditAllocationModal, setShowEditAllocationModal] = useState(false);
const [editingAllocation, setEditingAllocation] = useState<Allocation | null>(null);
const [editForm, setEditForm] = useState({
  mukkadam_id: 0,
  allocated_date: '',
  allocated_workers: 0,
  allocated_area: 0,
  mukkadam_rate: 0,
});
const [maxCapacity, setMaxCapacity] = useState<number | null>(null);
const [availableWorkers, setAvailableWorkers] = useState<number | null>(null);

// Fetch capacity when mukkadam or date changes
useEffect(() => {
  if (!editingAllocation || !editForm.mukkadam_id || !editForm.allocated_date) {
    setMaxCapacity(null);
    setAvailableWorkers(null);
    return;
  }

  const fetchCapacity = async () => {
    try {
      const mukkadam = mukkadams.find(m => m.mukkadam_id === editForm.mukkadam_id);
      if (!mukkadam) return;

      // Get remaining capacity
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadams/${editForm.mukkadam_id}/remaining_capacity/?date=${editForm.allocated_date}&cluster_id=${clusterId}`
      );
      const data = await res.json();
      const available = data.available_crew_size as number;

      // Get productivity for this activity
      const activity = (allJobs || jobs)
        .find(j => j.job_id === editingAllocation.job_id)
        ?.activities?.find(a => a.activity_name === editingAllocation.activity_name);

      if (!activity) return;

      const rate = mukkadam.activity_rates?.find(
        (r: any) =>
          r.activity_id === activity.activity_id ||
          r.activity_name === activity.activity_name
      );

      if (rate) {
        const productivity = Number(rate.productivity_per_worker);
        const maxArea = editForm.allocated_workers * productivity;
        
        setMaxCapacity(maxArea);
        setAvailableWorkers(available);
        
        // Auto-update mukkadam rate
        setEditForm(prev => ({
          ...prev,
          mukkadam_rate: Number(rate.rate_per_acre)
        }));
      }
    } catch (error) {
      console.error('Failed to fetch capacity:', error);
    }
  };

  fetchCapacity();
}, [editForm.mukkadam_id, editForm.allocated_date, editForm.allocated_workers, editingAllocation]);

// Handle edit allocation
const handleEditAllocation = async () => {
  if (!editingAllocation) return;

  // Validate area
  if (maxCapacity !== null && editForm.allocated_area > maxCapacity) {
    toast.error(
      `Area (${editForm.allocated_area.toFixed(2)} ac) exceeds capacity (${maxCapacity.toFixed(2)} ac)`
    );
    return;
  }

  // Validate workers
  if (availableWorkers !== null && editForm.allocated_workers > availableWorkers) {
    toast.error(
      `Only ${availableWorkers} workers available on ${editForm.allocated_date}`
    );
    return;
  }

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/allocations/${editingAllocation.id}/update_allocation/?cluster_id=${clusterId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      toast.error(data.error || 'Failed to update allocation');
      return;
    }

    toast.success('Allocation updated successfully!');
    setShowEditAllocationModal(false);
    setEditingAllocation(null);
    // onLeavesUpdated(); // Refresh allocations
  } catch (error) {
    toast.error('Failed to update allocation');
    console.error(error);
  }
};



  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content day-detail-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3 className="modal-title">{dateStr}</h3>
            <p className="modal-subtitle">Capacity: {capacitySummary.used}/{capacitySummary.total} workers</p>
          </div>
          <button onClick={onClose} className="modal-close"><X size={20} /></button>
        </div>

<div className="modal-tabs">
  <button
    className={`modal-tab ${activeTab === 'allocations' ? 'active' : ''}`}
    onClick={() => setActiveTab('allocations')}
  >
    Allocations ({filteredAllocations.length})
  </button>

  <button
    className={`modal-tab ${activeTab === 'jobs' ? 'active' : ''}`}
    onClick={() => setActiveTab('jobs')}
  >
    Jobs ({jobsOnThisDay.length})
  </button>

  <button
    className={`modal-tab ${activeTab === 'conflicts' ? 'active' : ''}`}
    onClick={() => setActiveTab('conflicts')}
  >
    Conflicts ({
      capacitySummary.conflicts.length +
      overloads.filter((o: any) => o.overloaded).length
    })
  </button>

  <button
    className={`modal-tab ${activeTab === 'potential' ? 'active' : ''}`}
    onClick={() => setActiveTab('potential')}
  >
    Potential ({potentialJobs ? potentialJobs.length : 0})
  </button>
</div>

<div className="modal-body-scroll">
  {/* TAB 1: ALLOCATIONS */}
  {activeTab === 'allocations' && (
    <div className="tab-content">
      {/* Leaves Section */}
      {leaves.length > 0 && (
        <div className="leave-section-mini">
          {leaves.map(l => (
            <div key={l.id} className="leave-alert-row">
              {l.leave_type === 'general' ? (
                <span>🏖️ <strong>Holiday:</strong> {l.reason}</span>
              ) : (
                <span>👤 <strong>{l.mukkadam_name}:</strong> {l.crew_on_leave} workers on leave</span>
              )}
            </div>
          ))}
        </div>
      )}


        {filteredAllocations.map(a => {
  const m = mukkadams.find(mk => mk.mukkadam_id === a.mukkadam);
  const job = (allJobs || jobs).find(j => j.job_id === a.job_id); // ✅ Use allJobs

  return (
    <div key={a.id} className="allocation-row card-style">
      <div className="allocation-main">
        <div className="item-title"><Tractor size={14} /> {a.activity_name}</div>
        
        <div className="item-farmer" style={{ fontSize: '0.85rem', color: '#475569', margin: '4px 0' }}>
          <span className="item-plot">{job?.plot_name || 'Unknown Plot'}</span>--
          <span className="item-plot">{job?.crop_name || 'Unknown Crop'}</span>--
          <span className="item-plot">{job?.variety || 'Unknown Variety'}</span>--
          <User size={12} style={{ marginRight: '4px' }} /> 
          <strong>{job?.farmer_name || 'Unknown Farmer'}</strong>
        </div>

        <div className="item-meta">{a.allocated_area} ac • {a.allocated_workers} workers</div>
        <div className="item-sub">Team: {m?.mukkadam_name || 'N/A'}</div>
      </div>
      <div className="allocation-actions">
        <button
    className="btn-link"
    onClick={() => {
      setEditingAllocation(a);
      setEditForm({
        mukkadam_id: a.mukkadam,
        allocated_date: a.allocated_date,
        allocated_workers: a.allocated_workers,
        allocated_area: a.allocated_area,
        mukkadam_rate: a.mukkadam_rate,
      });
      setShowEditAllocationModal(true);
    }}
  >
    Edit
  </button>
        <button className="btn-link" onClick={() => onAllocationDateChange(a)}>Move</button>
        <button className="btn-link delete" onClick={() => onAllocationDelete(a)}>Remove</button>
      </div>
    </div>



  );
})}

{/* Edit Allocation Modal */}
{showEditAllocationModal && editingAllocation && (
  <div className="modal-overlay" onClick={() => setShowEditAllocationModal(false)}>
    <div className="modal-content modal-md" onClick={(e) => e.stopPropagation()}>
      <div className="modal-header">
        <h3 className="modal-title">Edit Allocation</h3>
        <button onClick={() => setShowEditAllocationModal(false)} className="modal-close">
          <X size={20} />
        </button>
      </div>

      <div className="modal-body">
        {/* Activity (Read-only) */}
        <div className="form-group">
          <label className="form-label">Activity</label>
          <input
            type="text"
            value={editingAllocation.activity_name}
            className="form-input"
            disabled
            style={{ backgroundColor: '#f3f4f6', cursor: 'not-allowed' }}
          />
        </div>

        {/* Mukkadam */}
        <div className="form-group">
          <label className="form-label">Mukkadam *</label>
          <select
            className="form-select"
            value={editForm.mukkadam_id}
            onChange={(e) => {
              const id = parseInt(e.target.value);
              setEditForm({ ...editForm, mukkadam_id: id });
            }}
            required
          >
            <option value="">Select mukkadam</option>
            {mukkadams.map((m) => (
              <option key={m.mukkadam_id} value={m.mukkadam_id}>
                {m.mukkadam_name} (Crew: {m.crew_size})
              </option>
            ))}
          </select>
          {Number(editForm.mukkadam_rate) > 0 && (
  <small className="form-help" style={{ color: '#10b981' }}>
    Rate: ₹{Number(editForm.mukkadam_rate).toFixed(2)}/acre
  </small>
)}

        </div>

        {/* Date */}
        <div className="form-group">
          <label className="form-label">Date *</label>
          <input
            type="date"
            className="form-input"
            value={editForm.allocated_date}
            onChange={(e) => setEditForm({ ...editForm, allocated_date: e.target.value })}
            required
          />
        </div>

        {/* Workers */}
        <div className="form-group">
          <label className="form-label">Workers *</label>
          <input
            type="number"
            className="form-input"
            value={editForm.allocated_workers}
            onChange={(e) => {
              const workers = parseInt(e.target.value) || 0;
              setEditForm({ ...editForm, allocated_workers: workers });
            }}
            required
          />
          {availableWorkers !== null && (
            <small className="form-help">
              Available on {editForm.allocated_date}: {availableWorkers} workers
              {editForm.allocated_workers > availableWorkers && (
                <span style={{ color: '#dc2626', display: 'block' }}>
                  ⚠️ Exceeds available capacity
                </span>
              )}
            </small>
          )}
        </div>

        {/* Area */}
        <div className="form-group">
          <label className="form-label">Area (acres) *</label>
          <input
            type="number"
            step="0.01"
            className="form-input"
            value={editForm.allocated_area}
            onChange={(e) => {
              const area = parseFloat(e.target.value) || 0;
              setEditForm({ ...editForm, allocated_area: area });
            }}
            required
          />
          {maxCapacity !== null && (
            <small className="form-help">
              Max capacity with {editForm.allocated_workers} workers: {maxCapacity.toFixed(2)} acres
              {editForm.allocated_area > maxCapacity && (
                <span style={{ color: '#dc2626', display: 'block' }}>
                  ⚠️ Exceeds team capacity
                </span>
              )}
            </small>
          )}
        </div>

        {/* Summary */}
        <div className="allocation-summary" style={{
          padding: '1rem',
          backgroundColor: '#f0f9ff',
          borderRadius: '8px',
          marginTop: '1rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span>Farmer Rate:</span>
            <strong>₹{editingAllocation.farmer_rate}/acre</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span>Mukkadam Rate:</span>
            <strong>
  ₹{typeof editForm.mukkadam_rate === "number"
    ? editForm.mukkadam_rate.toFixed(2)
    : "0.00"}
  /acre
</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '0.5rem', borderTop: '1px solid #cbd5e1' }}>
            <span>Profit Margin:</span>
            <strong style={{ color: '#10b981' }}>
              ₹{((editingAllocation.farmer_rate - editForm.mukkadam_rate) * editForm.allocated_area).toFixed(2)}
            </strong>
          </div>
        </div>
      </div>

      <div className="modal-footer">
        <button
          onClick={() => {
            setShowEditAllocationModal(false);
            setEditingAllocation(null);
          }}
          className="btn-secondary"
        >
          Cancel
        </button>
        <button
          onClick={handleEditAllocation}
          className="btn-primary"
          disabled={
            !editForm.mukkadam_id ||
            !editForm.allocated_date ||
            editForm.allocated_workers <= 0 ||
            editForm.allocated_area <= 0 ||
            (maxCapacity !== null && editForm.allocated_area > maxCapacity) ||
            (availableWorkers !== null && editForm.allocated_workers > availableWorkers)
          }
        >
          Save Changes
        </button>
      </div>
    </div>
  </div>
)}
    </div>
  )}

  {/* TAB 2: JOBS */}
  {activeTab === 'jobs' && (
    <div className="tab-content">
      {jobsOnThisDay.length === 0 ? (
        <p className="empty-text">No jobs scheduled.</p>
      ) : (
        jobsOnThisDay.map(job => (
          <div 
            key={job.job_id} 
            className="job-card card-style clickable-job-card" 
            onClick={() => {
              const activity = job.activities.find(act => act.scheduled_date === isoDate);
              if (activity) {
                onStartAllocation(job.job_id, activity.id, activity);
              }
            }}
          >
            <div className="job-card-header">
              <span className="farmer-name">
                <User size={14} /> {job.farmer_name}
              </span>
              <span className="allocate-badge">Allocate →</span>
            </div>

            <div className="job-plot">
              {job.plot_name || job.job_id || 'Unknown plot'}--
              <span className="item-plot">{job?.crop_name || 'Unknown Crop'}</span>--
              <span className="item-plot">{job?.variety || 'Unknown Variety'}</span>
            </div>

            {job.activities
              .filter(act => act.scheduled_date === isoDate)
              .map(act => {
                const progress = (Number(act.allocated_area) / Number(act.total_area || 1)) * 100;
                return (
                  <div key={act.id} className="job-activity-item">
                    <div className="activity-info">
                      <span className="act-name">{act.activity_name}</span>
                      <span className="act-area">
                        {act.allocated_area}/{act.total_area} ac
                      </span>
                    </div>
                    <div className="progress-container">
                      <div className="progress-bar-bg">
                        <div
                          className="progress-bar-fill"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      <span className="progress-text">
                        {progress.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                );
              })}
          </div>
        ))
      )}
    </div>
  )}

  {/* TAB 3: CONFLICTS */}
  {activeTab === 'conflicts' && (
    <div className="tab-content">
      {capacitySummary.conflicts.length === 0 && overloads.length === 0 ? (
        <p className="empty-text">No conflicts detected.</p>
      ) : (
        <>
          {capacitySummary.conflicts.map((conflict, idx) => (
            <div key={`cap-${idx}`} className="conflict-row card-style warning">
              <AlertCircle size={16} color="#ef4444" />
              <div>
                <strong>{conflict.mukkadam}</strong>
                <p>
                  {conflict.type === 'overload'
                    ? `Overload: ${conflict.activity} (needed ${conflict.needed.toFixed(2)} ac, capacity ${conflict.available.toFixed(2)} ac)`
                    : conflict.message}
                </p>
              </div>
            </div>
          ))}

          {overloads
            .filter(o => o.overloaded)
            .map((o, idx) => (
              <div key={`ol-${idx}`} className="conflict-row card-style warning">
                <AlertCircle size={16} color="#f97316" />
                <div>
                  <strong>{o.activity_name}</strong>
                  <p>plot {o.plot_name} – {o.farmer_name}</p>
                  <p>
                    Remaining: {o.remaining_area} ac, capacity: {o.available_capacity_area} ac,
                    deficit: {o.deficit} ac {o.overloaded ? '(OVERLOADED)' : ''}
                  </p>
                </div>
              </div>
            ))}
        </>
      )}
    </div>
  )}

  {/* TAB 4: POTENTIAL */}
  {activeTab === 'potential' && (
    <div className="tab-content">
      {(!potentialJobs || potentialJobs.length === 0) ? (
        <p className="empty-text">No potential jobs.</p>
      ) : (
        <div className="section">
          <h3 className="section-title">
            Potential Jobs (remaining / not done)
          </h3>

          <div className="potential-grid">
            {potentialJobs.map(p => (
              <div
                key={`${p.jobId}-${p.activityId}-${p.plotId}`}
                className={`potential-card ${p.status === 'NONE' ? 'status-red' : 'status-yellow'}`}
              >
                <div className="potential-card-header">
                  <div className="activity-title">
                    {p.activityName}
                  </div>
                  <span className="status-pill">
                    {p.status === 'NONE' ? 'Not started' : 'Partially done'}
                  </span>
                </div>

                <div className="potential-meta">
                  <span className="meta-item">
                    <span className="meta-label">Farmer</span>
                    <span className="meta-value">{p.farmerName}</span>
                  </span>
                  <span className="meta-item">
                    <span className="meta-label">Plot</span>
                    <span className="meta-value">{p.plotName}</span>
                  </span>
                  <span className="meta-item">
                    <span className="meta-label">Crop</span>
                    <span className="meta-value">{p.cropName}</span>
                  </span>
                  <span className="meta-item">
                    <span className="meta-label">Variety</span>
                    <span className="meta-value">{p.variety}</span>
                  </span>
                </div>

                <div className="potential-stats">
                  <div className="stat">
                    <div className="stat-label">Unbooked area</div>
                    <div className="stat-value">
                      {p.unbookedArea} <span className="stat-unit">ac</span>
                    </div>
                  </div>
                  <div className="stat">
                    <div className="stat-label">Rate</div>
                    <div className="stat-value">
                      ₹{p.clusterRate}
                      <span className="stat-unit">/ac</span>
                    </div>
                  </div>
                  <div className="stat">
                    <div className="stat-label">Potential</div>
                    <div className="stat-value highlight">
                      ₹{p.potentialRevenue}
                    </div>
                  </div>
                </div>

                <div className="potential-footer">
                  <span className="job-id">Job: {p.jobId}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )}
</div>
      </div>
    </div>
  );
};
export default DayDetailModal;
