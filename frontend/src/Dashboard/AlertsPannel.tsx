import React from 'react';

export function AlertsPanel() {
  return (
    <div className="section">
      <h3>🚨 Conflicts & Alerts</h3>
      <div className="alerts-list">
        <div className="alert warning">
          <div className="alert-icon">⚠️</div>
          <div className="alert-content">
            <p className="alert-title">Ramesh Team: 5 free workers could help Dilip Farm</p>
            <p className="alert-subtitle">→ Save ₹800 by consolidating</p>
            <div className="alert-actions">
              <button className="btn-sm btn-primary">Auto-Assign</button>
              <button className="btn-sm btn-secondary">Dismiss</button>
            </div>
          </div>
        </div>

        <div className="alert info">
          <div className="alert-icon">☔</div>
          <div className="alert-content">
            <p className="alert-title">Rain forecast for Feb 11 in HEX_001</p>
            <p className="alert-subtitle">→ Affects 2 bookings (Sopan, Dilip)</p>
            <div className="alert-actions">
              <button className="btn-sm btn-primary">Reschedule Activities</button>
              <button className="btn-sm btn-secondary">Mark as Rain Day</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
