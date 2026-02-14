import React, { useState } from 'react';
// import { useApp } from '../../context/AppContext';
// import { BookingCard } from './BookingCard';
// import { NewBookingForm } from './NewBookingForm';
import './BookingList.css';
import { NewBookingForm } from './NewBookingForm';
import { BookingCard } from './BookingCard';
import { useApp } from '@/context/AppContext';

export function BookingsList() {
  const { bookings } = useApp();
  const [showNewForm, setShowNewForm] = useState(false);

  return (
    <div className="bookings-page">
      <div className="bookings-header">
        <h2>Bookings</h2>
        <button className="btn-primary" onClick={() => setShowNewForm(true)}>
          + New Booking
        </button>
      </div>

      {showNewForm && <NewBookingForm onClose={() => setShowNewForm(false)} />}

      <div className="bookings-list">
        {bookings.map((booking) => (
          <BookingCard key={booking.id} booking={booking} />
        ))}
      </div>
    </div>
  );
}
