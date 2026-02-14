// components/CapacityIndicator.tsx
import React from 'react';

interface CapacityIndicatorProps {
  workers: number;
  area: number;
  productivity: number;
}

const CapacityIndicator: React.FC<CapacityIndicatorProps> = ({
  workers,
  area,
  productivity
}) => {
  const maxCapacity = workers * productivity;
  const utilization = maxCapacity > 0 ? (area / maxCapacity) * 100 : 0;
  const canComplete = area <= maxCapacity;

  const getColorClass = () => {
    if (!canComplete) return 'danger';
    if (utilization > 90) return 'warning';
    return 'good';
  };

  return (
    <div className={`capacity-indicator ${getColorClass()}`}>
      <div className="capacity-header">
        <span className="capacity-title">Team Capacity</span>
        <span className="capacity-value">{maxCapacity.toFixed(2)} acres/day</span>
      </div>

      <div className="capacity-bar-container">
        <div className="capacity-bar">
          <div
            className={`capacity-fill ${getColorClass()}`}
            style={{ width: `${Math.min(utilization, 100)}%` }}
          />
        </div>
      </div>

      <div className="capacity-details">
        <span>{workers} workers × {productivity} acres/worker</span>
        <span className={canComplete ? 'text-success' : 'text-danger'}>
          {utilization.toFixed(0)}% utilized
        </span>
      </div>

      {!canComplete && (
        <div className="capacity-warning-message">
          ⚠️ Cannot complete {area} acres! Maximum capacity: {maxCapacity.toFixed(2)} acres
        </div>
      )}
    </div>
  );
};

export default CapacityIndicator;