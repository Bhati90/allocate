// components/AllocationModal.tsx
import React, { useState, useEffect } from 'react';
import { Job, Mukkadam } from '../types/types';
import CapacityIndicator from './CapacityIndicator';
import { API_BASE_URL } from '../types/config';

interface AllocationModalProps {
  jobs: Job[];
  mukkadams: Mukkadam[];
  selectedDate: Date;
  onClose: () => void;
  onCreate: (allocationData: any) => void;
  clusterId: number;
  initialJobId?: string;      
  initialActivityId?: number;
  initialDate?: string;  
  initialFarmerRate?: number;
  
}

const AllocationModal: React.FC<AllocationModalProps> = ({
  jobs,
  mukkadams,
  selectedDate,
  onClose,
  onCreate,
  clusterId,
  initialJobId,
  initialActivityId,
  initialDate,
  initialFarmerRate,
}) => {
  const [formData, setFormData] = useState({
  job_id: initialJobId || '',
  job_activity_id: initialActivityId || 0,
  allocated_date: initialDate || selectedDate.toISOString().split('T')[0],
  farmer_rate: initialFarmerRate || 0,
});


  // This Effect ensures that if the modal opens with a Job ID, 
  // it immediately finds the farmer and the rate.
useEffect(() => {
  if (initialJobId) {
    const job = jobs.find((j) => j.job_id === initialJobId);
    if (job) {
      setSelectedJob(job);
      const activity = job.activities?.find((a) => a.id === initialActivityId);
      if (activity) {
        setSelectedActivity(activity);
        setFormData(prev => ({
          ...prev,
          farmer_rate: initialFarmerRate ?? activity.rate_per_acre,
        }));
      }
    }
  }
}, [initialJobId, initialActivityId, initialFarmerRate, jobs]);


const [teams, setTeams] = useState([
  {
    mukkadam_id: 0,
    allocated_area: 0,
    allocated_workers: 0,
    mukkadam_rate: 0,
    allocated_date: initialDate || selectedDate.toISOString().split('T')[0],
  },
]);

const [teamHelpers, setTeamHelpers] = useState<
  Array<{
    availableWorkers: number | null;
    productivity: number | null;
    maxArea: number | null;
  }>
>([{ availableWorkers: null, productivity: null, maxArea: null }]);

  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [selectedActivity, setSelectedActivity] = useState<any>(null);

  useEffect(() => {
    if (formData.job_id) {
      const job = jobs.find((j) => j.job_id === formData.job_id);
      setSelectedJob(job || null);
    }
  }, [formData.job_id, jobs]);

  useEffect(() => {
    if (formData.job_activity_id && selectedJob) {
      const activity = selectedJob.activities?.find(
        (a) => a.id === formData.job_activity_id,
      );
      setSelectedActivity(activity || null);
      if (activity) {
        setFormData((prev) => ({ ...prev, farmer_rate: activity.rate_per_acre }));
      }
    }
  }, [formData.job_activity_id, selectedJob]);

  const updateTeam = (index: number, updates: Partial<(typeof teams)[number]>) => {
    setTeams((prev) =>
      prev.map((t, i) => (i === index ? { ...t, ...updates } : t)),
    );
  };
const addTeamRow = () => {
  const defaultDate = formData.allocated_date; // or selectedDate.toISOString().split('T')[0]
  setTeams(prev => [
    ...prev,
    {
      mukkadam_id: 0,
      allocated_area: 0,
      allocated_workers: 0,
      mukkadam_rate: 0,
      allocated_date: defaultDate,   // 👈 ensure not undefined
    },
  ]);
};

const removeTeamRow = (index: number) => {
  setTeams(prev => prev.filter((_, i) => i !== index));
  setTeamHelpers(prev => prev.filter((_, i) => i !== index));
};



const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();

  const validTeams = teams.filter(
    (t) => t.mukkadam_id && t.allocated_area > 0 && t.allocated_workers > 0
  );

  if (validTeams.length === 0) {
    alert('Please add at least one valid team allocation');
    return;
  }

  // ✅ Check total area doesn't exceed remaining area
  if (selectedActivity) {
    const totalAllocatingArea = validTeams.reduce(
      (sum, t) => sum + t.allocated_area,
      0
    );
    
    if (totalAllocatingArea > selectedActivity.remaining_area) {
      alert(
        `Cannot allocate ${totalAllocatingArea.toFixed(2)} acres.\n\n` +
        `Activity "${selectedActivity.activity_name}" only has ${selectedActivity.remaining_area} acres remaining.\n\n` +
        `You are trying to allocate ${(totalAllocatingArea - selectedActivity.remaining_area).toFixed(2)} acres more than available.`
      );
      return;
    }
  }

  // ✅ Check for general holidays
  const holidayErrors: string[] = [];
  const uniqueDates = [...new Set(validTeams.map(t => t.allocated_date))];
  
  for (const dateStr of uniqueDates) {
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/leaves/?start_date=${dateStr}&end_date=${dateStr}&cluster_id=${clusterId}`
      );
      const leaves = await res.json();
      
      const generalHoliday = leaves.find((l: any) => 
        l.date === dateStr && 
        l.leave_type === 'general' && 
        l.is_active
      );
      
      if (generalHoliday) {
        holidayErrors.push(
          `${dateStr}: ${generalHoliday.reason || 'General Holiday'} - Cannot allocate on this date`
        );
      }
    } catch (error) {
      console.error('Failed to check holidays:', error);
    }
  }

  if (holidayErrors.length > 0) {
    alert('Cannot create allocation on holiday(s):\n\n' + holidayErrors.join('\n'));
    return;
  }

  // ✅ Validate capacity for each team
  const validationErrors: string[] = [];
  
  for (let i = 0; i < validTeams.length; i++) {
    const team = validTeams[i];
    const teamIndex = teams.indexOf(team);
    const helper = teamHelpers[teamIndex];

    if (!helper.availableWorkers) {
      validationErrors.push(
        `Team ${i + 1}: Unable to check capacity for ${mukkadams.find(m => m.mukkadam_id === team.mukkadam_id)?.mukkadam_name}`
      );
      continue;
    }

    if (team.allocated_workers > helper.availableWorkers) {
      validationErrors.push(
        `Team ${i + 1} (${mukkadams.find(m => m.mukkadam_id === team.mukkadam_id)?.mukkadam_name} on ${team.allocated_date}): ` +
        `Requested ${team.allocated_workers} workers but only ${helper.availableWorkers} available`
      );
    }

    if (helper.maxArea != null && team.allocated_area > helper.maxArea) {
      validationErrors.push(
        `Team ${i + 1} (${mukkadams.find(m => m.mukkadam_id === team.mukkadam_id)?.mukkadam_name} on ${team.allocated_date}): ` +
        `Requested ${team.allocated_area.toFixed(2)} ac but max capacity is ${helper.maxArea.toFixed(2)} ac`
      );
    }
  }

  if (validationErrors.length > 0) {
    alert('Cannot create allocation:\n\n' + validationErrors.join('\n\n'));
    return;
  }

  // ✅ All validations passed
  const base = {
    job_id: formData.job_id,
    job_activity_id: formData.job_activity_id,
    farmer_rate: formData.farmer_rate,
  };

  const payload = validTeams.map((t) => ({
    ...base,
    allocated_date: t.allocated_date,
    mukkadam_id: t.mukkadam_id,
    allocated_area: t.allocated_area,
    allocated_workers: t.allocated_workers,
    mukkadam_rate: t.mukkadam_rate,
  }));

  onCreate(payload);
};
useEffect(() => {
const loadHelpers = async () => {
  if (!selectedActivity) return;

  const updated = await Promise.all(
    teams.map(async (team, idx) => {
      const dateStr = team.allocated_date;   // 👈 per team
      if (!team.mukkadam_id || !dateStr) {
        return { availableWorkers: null, productivity: null, maxArea: null };
      }

      try {
        const res = await fetch(
          `${API_BASE_URL}/api/mukkadams/${team.mukkadam_id}/remaining_capacity/?date=${dateStr}&cluster_id=${clusterId}`,
        );
        const data = await res.json();
        const available = data.available_crew_size as number;

        const mk = mukkadams.find(m => m.mukkadam_id === team.mukkadam_id);
        const rate = mk?.activity_rates?.find(
          (r: any) =>
            r.activity_id === selectedActivity.activity_id ||
            r.activity_name === selectedActivity.activity_name,
        );
        const productivity = rate ? Number(rate.productivity_per_worker) : null;
        const maxArea = productivity != null ? available * productivity : null;

        if (rate && !team.mukkadam_rate) {
          updateTeam(idx, { mukkadam_rate: Number(rate.rate_per_acre) });
        }

        return { availableWorkers: available, productivity, maxArea };
      } catch {
        return { availableWorkers: null, productivity: null, maxArea: null };
      }
    }),
  );

  setTeamHelpers(updated);
};


  loadHelpers();
}, [teams, selectedActivity, formData.allocated_date, mukkadams]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Create New Allocation</h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Job Selection */}
            <div className="form-group">
              <label className="form-label">Job</label>
              <select
                className="form-select"
                value={formData.job_id}
                onChange={(e) =>
                  setFormData({ ...formData, job_id: e.target.value })
                }
                required
              >
                <option value="">Select a job</option>
                {jobs.map((job) => (
                  <option key={job.job_id} value={job.job_id}>
                  - {job.farmer_name} - { job.plot_name ? job.plot_name : 'No plot info' }
                  </option>
                ))}
              </select>
            </div>

            {/* Activity Selection */}
            {selectedJob && (
              <div className="form-group">
                <label className="form-label">Activity</label>
                <select
                  className="form-select"
                  value={formData.job_activity_id}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      job_activity_id: parseInt(e.target.value),
                    })
                  }
                  required
                >
                  <option value="">Select an activity</option>
                  {selectedJob.activities?.map((activity) => (
                    <option key={activity.id} value={activity.id}>
                      {activity.activity_name} ({activity.remaining_area} ac remaining)
                      {activity.is_strict && ' [STRICT]'}
                    </option>
                  ))}
                </select>
              </div>
            )}

           

            {/* Farmer Rate */}
            <div className="form-group">
              <label className="form-label">Farmer Rate (₹/acre)</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.farmer_rate}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    farmer_rate: parseFloat(e.target.value),
                  })
                }
                required
              />
            </div>

            {/* Teams section */}
            <div className="form-divider">Teams for this day</div>

{teams.map((team, index) => {
  const selectedMukkadam = mukkadams.find(
    (m) => m.mukkadam_id === team.mukkadam_id,
  );
  const helper = teamHelpers[index] || {};
  const available = helper.availableWorkers;
  const productivity = helper.productivity;
  const maxArea = helper.maxArea;
  const workersForCalc = team.allocated_workers || 0;
  const maxAreaForEnteredWorkers =
    productivity != null ? workersForCalc * productivity : null;

  return (
    <div key={index} className="team-row">
      {/* Mukkadam */}
      <div className="form-group">
        <label className="form-label">Mukkadam</label>
        <select
          className="form-select"
          value={team.mukkadam_id || ''}
          onChange={(e) => {
            const id = parseInt(e.target.value);
            const mk = mukkadams.find((m) => m.mukkadam_id === id);
            updateTeam(index, {
              mukkadam_id: id,
              mukkadam_rate:
                mk && selectedActivity
                  ? mk.activity_rates?.find(
                      (r: any) =>
                        r.activity === selectedActivity.activity_id,
                    )?.rate_per_acre || 0
                  : team.mukkadam_rate,
            });
          }}
          required
        >
          <option value="">Select a mukkadam</option>
          {mukkadams.map((m) => (
            <option key={m.mukkadam_id} value={m.mukkadam_id}>
              {m.mukkadam_name} (Crew: {m.crew_size})
            </option>
          ))}
        </select>
        {selectedMukkadam && selectedActivity && (
          <span className="form-hint">
            Rate from rate card: ₹{team.mukkadam_rate.toFixed(2)} / acre
          </span>
        )}
      </div>
      {selectedMukkadam && selectedActivity && team.mukkadam_rate > 0 && (
    <div className="form-hint" style={{ 
      marginTop: '0.5rem', 
      padding: '0.5rem', 
      backgroundColor: '#f0fdf4', 
      borderLeft: '3px solid #22c55e',
      borderRadius: '4px'
    }}>
      <strong>Mukkadam Rate:</strong> ₹{team.mukkadam_rate.toFixed(2)} / acre
      <br />
      <small style={{ color: '#6b7280' }}>
        (From rate card for {selectedActivity.activity_name})
      </small>
    </div>
  )}
  {selectedActivity && (
  <div className="form-hint" style={{ 
    padding: '0.75rem', 
    backgroundColor: '#f0f9ff', 
    borderLeft: '3px solid #3b82f6',
    borderRadius: '4px',
    marginTop: '0.5rem'
  }}>
    <strong>Remaining area:</strong> {selectedActivity.remaining_area} acres
    <br />
    <small style={{ color: '#6b7280' }}>
      Total area being allocated: {teams.reduce((sum, t) => sum + t.allocated_area, 0).toFixed(2)} acres
    </small>
    {teams.reduce((sum, t) => sum + t.allocated_area, 0) > selectedActivity.remaining_area && (
      <div style={{ color: '#dc2626', marginTop: '0.5rem' }}>
        ⚠️ Warning: Allocating {(teams.reduce((sum, t) => sum + t.allocated_area, 0) - selectedActivity.remaining_area).toFixed(2)} acres more than available!
      </div>
    )}
  </div>
)}

      {/* 👇 ADD DATE INPUT HERE */}
      <div className="form-group">
        <label className="form-label">Date</label>
        <input
          type="date"
          className="form-input"
          value={team.allocated_date}
          onChange={(e) =>
            updateTeam(index, {
              allocated_date: e.target.value,
            })
          }
          required
        />
        {selectedActivity?.is_strict && teams.length > 1 && (
          <span className="form-hint" style={{ color: '#f59e0b' }}>
            ⚠️ STRICT activity: All teams must have the same date
          </span>
        )}
      </div>
      

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '1rem',
        }}
      >
        <div>
          <label className="form-label">Area (acres)</label>
          <input
            type="number"
            step="0.01"
            className="form-input"
            value={team.allocated_area}
            onChange={(e) =>
              updateTeam(index, {
                allocated_area: parseFloat(e.target.value) || 0,
              })
            }
            required
          />
          {maxArea != null && (
            <span className="form-hint">
              Max for full available team today: {maxArea.toFixed(2)} ac
            </span>
          )}
          {maxAreaForEnteredWorkers != null && workersForCalc > 0 && (
            <span className="form-hint">
              With {workersForCalc} workers: {maxAreaForEnteredWorkers.toFixed(2)} ac
            </span>
          )}
        </div>

        

        <div>
          <label className="form-label">Workers</label>
          

<input
  type="number"
  className="form-input"
  value={team.allocated_workers}
  onChange={(e) => {
    const workers = parseInt(e.target.value) || 0;
    const autoArea = productivity != null ? workers * productivity : 0;
    
    updateTeam(index, {
      allocated_workers: workers,
      allocated_area: parseFloat(autoArea.toFixed(2)), // ✅ Round to 2 decimals
    });
  }}
  max={available ?? selectedMukkadam?.crew_size ?? undefined}
  required
/>
          {available != null && (
            <span className="form-hint">
              Available today: {available} workers
            </span>
          )}
        </div>
      </div>

      {productivity != null && (
        <div className="form-hint">
          Productivity: {productivity.toFixed(3)} ac / worker / day
        </div>
      )}

      {/* Remove row */}
      {teams.length > 1 && (
        <button
          type="button"
          className="btn-secondary"
          onClick={() => removeTeamRow(index)}
        >
          Remove team
        </button>
      )}
    </div>
  );
})}
            <button
              type="button"
              className="btn-secondary"
              onClick={addTeamRow}
            >
              + Add another team
            </button>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
            >
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              Create Allocations
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};


export default AllocationModal;