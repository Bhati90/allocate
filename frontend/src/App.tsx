import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import Dashboard from "./Dashboard";

import Login from "./Login";

import AllocationView from './AllocationView';
import AllocationDashboard from "./AllocationDashboard";

import ProtectedRoute from "./ProtectedRoute";
import AdminRoute from "./AdminRoute";

import { AuthProvider } from "./context/auth";
// import AllocationAnalytics from "./analyatics";
import SupplyHealthDashboard from "./health";
import MukkadamScorecard from "./Score";
import MukkadamDetails from "./ScoreDetails";
import CallsPage from "./CallPage";
import TotalJobsView from "./Total";
import FarmScheduler from "./Farm";
import MukkadamManagement from "./MukkadamManagement";
import TenderFront from "./Tender";
// import MukkadamPerformanceDashboard from "./analyatics";
// import ActiveMukkadamsDashboard from "./analyatics";
const queryClient = new QueryClient();

// wrapper to read the route param and pass it to FarmerProfil

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <AuthProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter basename="/">
        <Routes>
          {/* <Route path="/loginf" element={<Login />} />
          
          <Route path="/analyatics" element={
            <AdminRoute><MukkadamScorecard /></AdminRoute>
          } /> */}

          <Route path="/" element={
           <TenderFront />
          } />
{/* 
          <Route path="/mukkadam" element={
            <AdminRoute><MukkadamManagement /></AdminRoute>
          } />

           <Route path="/calls" element={
            <AdminRoute><CallsPage /></AdminRoute>
          } />

          <Route path="/total-jobs" element={<TotalJobsView/>} />

          <Route path="/mukkadam-details/:mukkadamId" element={<AdminRoute><MukkadamDetails /></AdminRoute>} /> {/* ← Add this */}
        
          {/* <Route path="/allocations/new" element={<ProtectedRoute><AllocationDashboard /></ProtectedRoute>} />
           <Route path="/allocations/new" element={<ComplexAllocationDashboard />} />
          <Route path="/allocations/:id" element={<AllocationView />} />
          <Route path = '/health' element= {<SupplyHealthDashboard/>} />
          <Route path="/dashboard" element={
            <ProtectedRoute><Dashboard /></ProtectedRoute>
          } />  */}
          
          

          {/* <Route path="*" element={<Navigate to="/dashboard" />} /> */}
        </Routes>
      </BrowserRouter>
      </AuthProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;

// import React, { useState } from 'react';
// import { Layout } from './layout/Layout';
// import { Dashboard } from './Dashboard/Dashboard';
// import { MapView } from './components/Map/MapView';
// import { BookingsList } from './components/Booking/BookingList';
// import { DayWorkView } from './components/calender/DayWorkView';
// import { TeamsPage } from './components/Teams/TeamsPage';
// import { AppProvider, useApp } from './context/AppContext';
// import { HexMapView } from './components/Map/HexaMapView';
// import { JobsCalendarPage } from './components/calender/JobsPage';

// // Inner app that is allowed to use useApp()
// const InnerApp: React.FC = () => {
//   const { selectedDate } = useApp();          // ✅ now inside provider
//   const [currentPage, setCurrentPage] = useState('dashboard');

//   const renderPage = () => {
//     switch (currentPage) {
//       case 'dashboard':
//         return <Dashboard />;
//       case 'map':
//         return <MapView />;               // or MapView if you prefer
//       case 'bookings':
//         return <BookingsList />;
       
//       case 'calendar':
//         return <JobsCalendarPage />;
//       case 'teams':
//         return <TeamsPage />;
//       default:
//         return <Dashboard />;
//     }
//   };

//   return (
//     <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
//       {renderPage()}
//     </Layout>
//   );
// };

// function App() {
//   return (
//     <AppProvider>
//       <InnerApp />
//     </AppProvider>
//   );
// }

// export default App;
