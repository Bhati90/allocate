import React from 'react';
// import { Team } from '../../types';
// import { useApp } from '@/context/AppContext';
import { Team } from '../types/index';
import { useApp } from '@/context/AppContext';

interface TeamStatusCardProps {
  team: Team;
}

export function TeamStatusCard({ team }: TeamStatusCardProps) {
  const { bookings, farms } = useApp();

  // Mock: Check if team has work today
  const hasWork = team.id !== 'TEAM_004';
  const workersUsed = hasWork ? Math.floor(team.total_workers * 0.8) : 0;
  const workersFree = team.total_workers - workersUsed;

  const mockFarm = farms[0];

  return (
    <div className={`team-status-card ${hasWork ? 'active' : 'idle'}`}>
      <div className="team-header">
        <span className="status-badge">{hasWork ? '✅' : '🟡'}</span>
        <div>
          <h4>{team.name} ({team.total_workers})</h4>
          <p className="mukkadam-name">{team.mukkadam_name}</p>
        </div>
      </div>

      {hasWork ? (
        <div className="team-work-info">
          <p className="farm-location">📍 {mockFarm.location.village} - {mockFarm.farmer_name} Farm</p>
          <p className="activity-name">Land Preparation</p>
          <div className="worker-allocation">
            <span>Workers: {workersUsed}/{team.total_workers} used</span>
            <span className="free-workers">Free: {workersFree}</span>
          </div>
          <div className="progress-info">
            <span>📊 Day 2 of 3</span>
            <span className="status-tag on-track">On Track</span>
          </div>
          <div className="financials">
            <span>💰 Revenue: ₹2,000</span>
            <span>Cost: ₹1,600</span>
          </div>
          {workersFree >= 3 && (
            <button className="btn-secondary">Reallocate Free Workers</button>
          )}
        </div>
      ) : (
        <div className="team-idle">
          <p>No assignment today</p>
          <p className="suggestion">Available for booking</p>
          <button className="btn-primary">View Opportunities</button>
        </div>
      )}
    </div>
  );
}
