import { useApp } from '@/context/AppContext';
import React from 'react';
// import { useApp } from '@/context/AppContext';

export function QuickStats() {
  const { teams, bookings } = useApp();

  const totalWorkers = teams.reduce((sum, t) => sum + t.total_workers, 0);
  const activeTeams = teams.length;
  const deployedWorkers = Math.floor(totalWorkers * 0.62); // Mock calculation
  const freeWorkers = totalWorkers - deployedWorkers;
  const utilization = ((deployedWorkers / totalWorkers) * 100).toFixed(0);

  return (
    <div className="quick-stats">
      <div className="stat-card">
        <div className="stat-label">Teams Active</div>
        <div className="stat-value">{activeTeams - 1}/{activeTeams}</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Workers Deployed</div>
        <div className="stat-value">{deployedWorkers}/{totalWorkers}</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Utilization</div>
        <div className="stat-value">{utilization}%</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Free Workers</div>
        <div className="stat-value highlight">{freeWorkers}</div>
      </div>
    </div>
  );
}
