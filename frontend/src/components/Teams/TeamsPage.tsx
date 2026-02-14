import React from 'react';
// import { useApp } from '../../context/AppContext';
import './TeamsPage.css';
import { useApp } from '@/context/AppContext';

export function TeamsPage() {
  const { teams } = useApp();

  return (
    <div className="teams-page">
      <div className="teams-header">
        <h2>Teams</h2>
        <button className="btn-primary">+ Add Team</button>
      </div>

      <div className="teams-list">
        {teams.map((team) => (
          <div key={team.id} className="team-card">
            <div className="team-card-header">
              <h3>
                {team.name} ({team.id})
              </h3>
              <p className="mukkadam-info">
                📍 Base: {team.base_location.village} | 📞 {team.mukkadam_contact}
              </p>
              <p className="worker-count">Workers: {team.total_workers} | Monthly Cost: ₹{(team.total_workers * team.monthly_salary_per_worker).toLocaleString('en-IN')}</p>
            </div>

            <div className="team-stats">
              <h4>This Month:</h4>
              <div className="stats-grid">
                <div className="stat-item">
                  <span className="stat-label">Days Worked:</span>
                  <span className="stat-value">18/28 (64%)</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Acres Completed:</span>
                  <span className="stat-value">45.2</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Revenue:</span>
                  <span className="stat-value">₹1,12,000</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Farms Serviced:</span>
                  <span className="stat-value">8</span>
                </div>
              </div>
            </div>

            {team.specialization && (
              <div className="specialization">
                <strong>Specialization:</strong>{' '}
                {team.specialization.map((s) => s.replace('_', ' ')).join(', ')}
              </div>
            )}

            <div className="efficiency-grid">
              <h4>Efficiency Ratings:</h4>
              {Object.entries(team.efficiency_rating).map(([activity, rating]) => (
                <div key={activity} className="efficiency-item">
                  <span className="activity-label">{activity.replace('_', ' ')}:</span>
                  <div className="rating-bar">
                    <div
                      className="rating-fill"
                      style={{ width: `${(Number(rating) / 1.5) * 100}%` }}
                    ></div>
                  </div>
                  <span className="rating-value">{(Number(rating) * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>

            <div className="team-actions">
              <button className="btn-secondary">View Schedule</button>
              <button className="btn-secondary">Edit</button>
              <button className="btn-secondary">View Feedback History</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
