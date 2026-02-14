import React from 'react';
// import { useApp } from '../../context/AppContext';
// import { QuickStats } from './QuickStats';
// import { TeamStatusCard } from './TeamStatusCard';
// import { AlertsPanel } from './AlertsPanel';
// import { addDays, formatISO } from '../../utils/dateUtils';
import './Dashboard.css';
// import { useApp } from '@/context/AppContext';
import { addDays,formatISO } from '@/utils/dateUtils';
import { QuickStats } from './QuickStatus';
import { TeamStatusCard } from './TeamStatusCard';
import { AlertsPanel } from './AlertsPannel';
import { useApp } from '@/context/AppContext';

export function Dashboard() {
  const { selectedDate, setSelectedDate, teams, bookings, farms } = useApp();

  const goToPrevDay = () => {
    const date = new Date(selectedDate);
    setSelectedDate(formatISO(addDays(date, -1)));
  };

  const goToNextDay = () => {
    const date = new Date(selectedDate);
    setSelectedDate(formatISO(addDays(date, 1)));
  };

  const goToToday = () => {
    setSelectedDate(formatISO(new Date()));
  };

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>Dashboard - {new Date(selectedDate).toLocaleDateString('en-IN', { 
          weekday: 'long', 
          year: 'numeric', 
          month: 'long', 
          day: 'numeric' 
        })}</h2>
        <div className="date-controls">
          <button onClick={goToPrevDay}>◀</button>
          <button onClick={goToToday}>Today</button>
          <button onClick={goToNextDay}>▶</button>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          />
        </div>
      </div>

      <QuickStats />

      <div className="section">
        <h3>👥 Team Status Today</h3>
        <div className="team-cards">
          {teams.map((team) => (
            <TeamStatusCard key={team.id} team={team} />
          ))}
        </div>
      </div>

      <AlertsPanel />
    </div>
  );
}
