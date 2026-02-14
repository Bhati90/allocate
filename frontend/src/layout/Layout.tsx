import React, { ReactNode, useState } from 'react';
import './Layout.css';

interface LayoutProps {
  children: ReactNode;
  currentPage: string;
  onNavigate: (page: string) => void;
}

export function Layout({ children, currentPage, onNavigate }: LayoutProps) {

const navItems = [
  { id: 'dashboard', label: '📅 Dashboard' },
  { id: 'map', label: '🗺️ Map' },
  { id: 'calendar', label: '📆 Calendar' },   // ✅ new
  { id: 'bookings', label: '📋 Bookings' },
  { id: 'teams', label: '👥 Teams' },
];


  return (
    <div className="layout">
      <header className="header">
        <h1>🌾 Farm Labour Scheduler</h1>
        <div className="user-menu">
          <span>Admin</span>
        </div>
      </header>
      <nav className="nav">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <main className="main-content">{children}</main>
    </div>
  );
}
