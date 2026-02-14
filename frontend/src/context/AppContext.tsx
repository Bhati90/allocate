import React, { createContext, useContext, useState, ReactNode } from 'react';
import { Team, Farm, HexagonCluster, Booking, DisruptionEvent } from '../types/index';
// import { TEAMS } from '@/data/mockdata';
import { TEAMS, FARMS, HEXAGONS, INITIAL_BOOKINGS } from '@/data/mockdata';
// import { DisruptionEvent } from '../types';

interface AppContextType {
  teams: Team[];
  farms: Farm[];
  hexagons: HexagonCluster[];
  bookings: Booking[];
  disruptions: DisruptionEvent[];
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  addBooking: (booking: Booking) => void;
  updateBooking: (id: string, updates: Partial<Booking>) => void;
  addDisruption: (disruption: DisruptionEvent) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [teams] = useState<Team[]>(TEAMS);
  const [farms] = useState<Farm[]>(FARMS);
  const [hexagons] = useState<HexagonCluster[]>(HEXAGONS);
  const [bookings, setBookings] = useState<Booking[]>(INITIAL_BOOKINGS);

  const [disruptions, setDisruptions] = useState<DisruptionEvent[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('2026-02-10');

  const addBooking = (booking: Booking) => {
    setBookings((prev) => [...prev, booking]);
  };

  const updateBooking = (id: string, updates: Partial<Booking>) => {
    setBookings((prev) =>
      prev.map((b) => (b.id === id ? { ...b, ...updates } : b))
    );
  };

  const addDisruption = (disruption: DisruptionEvent) => {
    setDisruptions((prev) => [...prev, disruption]);
  };

  return (
    <AppContext.Provider
      value={{
        teams,
        farms,
        hexagons,
        bookings,
        disruptions,
        selectedDate,
        setSelectedDate,
        addBooking,
        updateBooking,
        addDisruption,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}
