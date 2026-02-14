import React from 'react';
import { Booking, ACTIVITY_CONFIGS } from '../../types/index';
// import { useApp } from '../../context/AppContext';
import { formatDisplayDate } from '../../utils/dateUtils';
import { useApp } from '@/context/AppContext';

interface BookingCardProps {
  booking: Booking;
}

export function BookingCard({ booking }: BookingCardProps) {
  const { farms } = useApp();
  const farm = farms.find((f) => f.id === booking.farm_id);

  if (!farm) return null;

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { label: string; className: string }> = {
      pending: { label: 'Pending', className: 'badge-pending' },
      in_progress: { label: 'In Progress', className: 'badge-progress' },
      completed: { label: 'Completed', className: 'badge-completed' },
      cancelled: { label: 'Cancelled', className: 'badge-cancelled' },
    };
    const badge = badges[status] || badges.pending;
    return <span className={`badge ${badge.className}`}>{badge.label}</span>;
  };

  return (
    <div className="booking-card">
      <div className="booking-header">
        <div>
          <h3>
            {booking.id} | {farm.farmer_name} - {farm.location.village}
          </h3>
          <p className="crop-info">
            {booking.crop_type.charAt(0).toUpperCase() + booking.crop_type.slice(1)} |{' '}
            {booking.total_acres} acres
          </p>
        </div>
        {getStatusBadge(booking.status)}
      </div>

      <div className="booking-timeline">
        <h4>Timeline:</h4>
        {ACTIVITY_CONFIGS.map((config, index) => (
          <div key={config.type} className="timeline-item">
            <span className="timeline-icon">
              {index < 2 ? '✅' : index === 2 ? '🔄' : '⏳'}
            </span>
            <span className="activity-name">{config.display_name}</span>
            <span className="activity-status">
              {index < 2 ? 'Completed' : index === 2 ? 'Ongoing' : 'Not started'}
            </span>
          </div>
        ))}
      </div>

      <div className="booking-financials">
        <div>
          <span className="label">Revenue:</span>
          <span className="value">₹{booking.total_revenue.toLocaleString('en-IN')}</span>
        </div>
        <div>
          <span className="label">Cost:</span>
          <span className="value">₹{booking.total_cost.toLocaleString('en-IN')}</span>
        </div>
        <div>
          <span className="label">Profit:</span>
          <span className="value profit">
            ₹{(booking.total_revenue - booking.total_cost).toLocaleString('en-IN')}
          </span>
        </div>
        <div>
          <span className="label">Margin:</span>
          <span className="value">{booking.profit_margin.toFixed(1)}%</span>
        </div>
      </div>

      <div className="booking-actions">
        <button className="btn-secondary">View Details</button>
        <button className="btn-secondary">Edit</button>
      </div>
    </div>
  );
}
