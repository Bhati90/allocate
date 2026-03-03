// components/LeaveModal.tsx
import React, { useState } from 'react';
import { X, Calendar } from 'lucide-react';
import toast from 'react-hot-toast';
import { Mukkadam } from '../types/types';
import { API_BASE_URL } from '@/types/config';

interface Props {
  selectedDate: Date;
  mukkadams: Mukkadam[];
  existingLeaves: any[];
  onClose: () => void;
  onLeaveMarked: () => void;
  clusterId: number;  
}

const LeaveModal: React.FC<Props> = ({
  selectedDate,
  mukkadams,
  existingLeaves,
  onClose,
  onLeaveMarked,
  clusterId, 
}) => {
  const [leaveType, setLeaveType] = useState<'mukkadam' | 'general'>('mukkadam');
  const [selectedMukkadam, setSelectedMukkadam] = useState<number | null>(null);
  const [reason, setReason] = useState('');
const [crewOnLeave, setCrewOnLeave] = useState<number>(0);

const [availableWorkers, setAvailableWorkers] = useState<number>(0);

// Fetch available workers when mukkadam is selected
const fetchAvailableWorkers = async (mukkadamId: number) => {
  try {
    const dateStr = formatDate(selectedDate);
    const res = await fetch(
      `${API_BASE_URL}/api/mukkadams/daily_capacity_all/?date=${dateStr}&cluster_id=${clusterId}`
    );
    const data = await res.json();
    const entry = (data as any[]).find(d => d.mukkadam_id === mukkadamId);
    const avail = entry ? entry.available_crew_size : 0;
    setAvailableWorkers(avail);
    setCrewOnLeave(avail); // default to all available
  } catch (e) {
    // fallback to crew_size
    const mk = mukkadams.find(m => m.mukkadam_id === mukkadamId);
    const fallback = mk?.crew_size || 0;
    setAvailableWorkers(fallback);
    setCrewOnLeave(fallback);
  }
};
const formatDate = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};
  // Check existing leaves for this date
const existingLeaveForDate = existingLeaves.find((leave) => {
  const sameDate = leave.date === formatDate(selectedDate);

  if (!sameDate) return false;

  if (leaveType === 'general') {
    return leave.leave_type === 'general';
  }

  // mukkadam-specific: same type + same mukkadam
  return (
    leave.leave_type === 'mukkadam' &&
    selectedMukkadam &&
    Number(leave.mukkadam) === Number(selectedMukkadam)
  );
});


const handleMarkLeave = async () => {
  if (leaveType === 'mukkadam' && !selectedMukkadam) {
    toast.error('Please select a mukkadam');
    return;
  }

  const selected = selectedMukkadam
    ? mukkadams.find(m => m.mukkadam_id === selectedMukkadam)
    : null;
  const maxCrew = selected ? selected.crew_size : 0;

  const safeCrewOnLeave =
  leaveType === 'mukkadam'
    ? Math.min(Math.max(0, crewOnLeave || 0), availableWorkers) // ← use availableWorkers
    : 0;

  const payload = {
    date: formatDate(selectedDate),
    leave_type: leaveType,
    mukkadam: leaveType === 'mukkadam' ? selectedMukkadam : null,
    reason: reason || 'Leave marked',
    crew_on_leave: safeCrewOnLeave,
    is_active: true,
    cluster: clusterId,
  };




  const url = existingLeaveForDate
  ? `${API_BASE_URL}/api/leaves/${existingLeaveForDate.id}/`
  : `${API_BASE_URL}/api/leaves/`;

const method = existingLeaveForDate ? 'PATCH' : 'POST';

  try {
    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      toast.success(
        leaveType === 'general'
          ? 'General holiday saved!'
          : 'Mukkadam leave saved!'
      );
      onLeaveMarked();
            window.location.reload();
      onClose();
    } else {
      const err = await response.json().catch(() => null);
      console.error(err);
      toast.error('Failed to save leave');
    }
  } catch (error) {
    toast.error('Failed to save leave');
    console.error(error);
  }
};

  const handleRemoveLeave = async (leaveId: number) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/leaves/${leaveId}/`,
        { method: 'DELETE' }
      );

      if (response.ok) {
        toast.success('Leave removed!');
        onLeaveMarked();
              window.location.reload();
      } else {
        toast.error('Failed to remove leave');
      }
    } catch (error) {
      toast.error('Failed to remove leave');
      console.error(error);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-wrapper">
            <Calendar size={20} />
            <h3 className="modal-title">
              Manage Leave - {selectedDate.toLocaleDateString()}
            </h3>
          </div>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Show existing leaves */}
          {existingLeaveForDate && (
            <div className="existing-leaves-section">
              <h4 className="section-subtitle">Existing Leaves</h4>
              <div className="leave-item">
                <div className="leave-info">
                  {existingLeaveForDate.leave_type === 'general' ? (
                    <span className="leave-badge general">
                      🏖️ General Holiday
                    </span>
                  ) : (
                    <span className="leave-badge mukkadam">
                      👤 {existingLeaveForDate.mukkadam_name}
                    </span>
                  )}
                  {existingLeaveForDate.reason && (
                    <span className="leave-reason">{existingLeaveForDate.reason} ({existingLeaveForDate.crew_on_leave} workers on leave)</span>
                  )}
                </div>
                <button
                  onClick={() => handleRemoveLeave(existingLeaveForDate.id)}
                  className="btn-danger-sm"
                >
                  Remove
                </button>
              </div>
            </div>
          )}

          <div className="form-divider">Mark New Leave</div>

          {/* Leave Type Selection */}
          <div className="form-group">
            <label className="form-label">Leave Type</label>
            <div className="radio-group">
              <label className="radio-label">
                <input
                  type="radio"
                  name="leaveType"
                  checked={leaveType === 'mukkadam'}
                  onChange={() => setLeaveType('mukkadam')}
                />
                <span>Specific Mukkadam</span>
              </label>
              <label className="radio-label">
                <input
                  type="radio"
                  name="leaveType"
                  checked={leaveType === 'general'}
                  onChange={() => setLeaveType('general')}
                />
                <span>General Holiday</span>
              </label>
            </div>
          </div>

          {leaveType === 'mukkadam' && (
  <>
    <div className="form-group">
      <label className="form-label">Select Mukkadam *</label>
      <select
  value={selectedMukkadam || ''}
  onChange={(e) => {
    const id = Number(e.target.value);
  setSelectedMukkadam(id);
  fetchAvailableWorkers(id);
    const mk = mukkadams.find(m => m.mukkadam_id === id);
    setCrewOnLeave(mk ? mk.crew_size : 0);
  }}
  className="form-select"
  required
>
  <option value="">Select mukkadam</option>
  {mukkadams.map((mukkadam) => (
    <option key={mukkadam.mukkadam_id} value={mukkadam.mukkadam_id}>
      {mukkadam.mukkadam_name} ({mukkadam.crew_size} workers)
    </option>
  ))}
</select>

    </div>

    <div className="form-group">
  <label className="form-label">
    Workers on leave
    <span style={{ fontSize: '0.72rem', color: '#6b7280', marginLeft: '6px' }}>
      (max: {availableWorkers} available today)
    </span>
  </label>
  <input
    type="number"
    min={0}
    max={availableWorkers}
    value={crewOnLeave}
    onChange={(e) => {
      const val = Number(e.target.value) || 0;
      setCrewOnLeave(Math.min(val, availableWorkers)); // hard cap
    }}
    className="form-input"
  />
  {crewOnLeave > availableWorkers && (
    <p style={{ color: '#dc2626', fontSize: '0.72rem', marginTop: '4px' }}>
      ⚠ Cannot exceed {availableWorkers} available workers
    </p>
  )}
</div>
  </>
)}


          {/* Reason */}
          <div className="form-group">
            <label className="form-label">Reason (Optional)</label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="form-input"
              placeholder="Personal leave, Festival, etc."
            />
          </div>

          {/* Info Box */}
          <div className="info-box">
            {leaveType === 'general' ? (
              <p>
                ⚫ General holiday will block <strong>all mukkadams</strong> for this date.
                No allocations can be created.
              </p>
            ) : (
              <p>
                🔵 Mukkadam leave will block only <strong>selected mukkadam</strong> for
                this date. Other mukkadams remain available.
              </p>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button onClick={handleMarkLeave} className="btn-primary">
            Mark Leave
          </button>
        </div>
      </div>
    </div>
  );
};

export default LeaveModal;