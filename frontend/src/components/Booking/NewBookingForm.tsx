import React, { useState } from 'react';
// import { useApp } from '../../context/AppContext';
import { suggestBestTeam } from '../../utils/businessLogic';
import { useApp } from '@/context/AppContext';

interface NewBookingFormProps {
  onClose: () => void;
}

export function NewBookingForm({ onClose }: NewBookingFormProps) {
  const { farms, teams, hexagons, addBooking } = useApp();
  const [selectedFarm, setSelectedFarm] = useState('');
  const [acres, setAcres] = useState('');
  const [startDate, setStartDate] = useState('');

  const handleSubmit = () => {
    if (!selectedFarm || !acres || !startDate) {
      alert('Please fill all fields');
      return;
    }

    const farm = farms.find((f) => f.id === selectedFarm)!;
    const newBooking = {
      id: `BOOK_${Date.now()}`,
      farm_id: selectedFarm,
      crop_type: farm.crop_type,
      total_acres: parseFloat(acres),
      booking_date: new Date().toISOString().split('T')[0],
      status: 'pending' as const,
      total_cost: 0,
      total_revenue: 0,
      profit_margin: 0,
      notes: '',
      activities: [],
    };

    addBooking(newBooking);
    onClose();
  };

  const farm = farms.find((f) => f.id === selectedFarm);
  const suggestions = farm
    ? suggestBestTeam(farm, teams, hexagons, 'land_prep', parseFloat(acres) || 1)
    : [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create New Booking</h2>
          <button className="close-btn" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="form-section">
          <h3>Step 1: Farm Details</h3>
          <label>
            Select Farm:
            <select value={selectedFarm} onChange={(e) => setSelectedFarm(e.target.value)}>
              <option value="">Choose a farm...</option>
              {farms.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.farmer_name} - {f.location.village} ({f.crop_type}, {f.total_acres} acres)
                </option>
              ))}
            </select>
          </label>

          <label>
            Total Acres:
            <input
              type="number"
              step="0.1"
              value={acres}
              onChange={(e) => setAcres(e.target.value)}
              placeholder="5.5"
            />
          </label>
        </div>

        <div className="form-section">
          <h3>Step 2: Schedule</h3>
          <label>
            Start Date (Activity 1):
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </label>
        </div>

        {suggestions.length > 0 && (
          <div className="form-section">
            <h3>Step 3: Suggested Teams</h3>
            {suggestions.slice(0, 2).map((s) => {
              const team = teams.find((t) => t.id === s.team_id)!;
              return (
                <div key={s.team_id} className="team-suggestion">
                  <div>
                    <strong>{team.name}</strong> (Score: {s.score.toFixed(0)}/100)
                  </div>
                  <div className="suggestion-reasons">
                    {s.reasons.map((r, i) => (
                      <span key={i} className="reason-tag">
                        {r}
                      </span>
                    ))}
                  </div>
                  <div>Cost: ₹{s.cost.toLocaleString('en-IN')}</div>
                </div>
              );
            })}
          </div>
        )}

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleSubmit}>
            Create Booking
          </button>
        </div>
      </div>
    </div>
  );
}
