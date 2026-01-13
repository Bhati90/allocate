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
          <Route path="/login" element={<Login />} />
          
          {/* <Route path="/analyatics" element={
            <ProtectedRoute><ActiveMukkadamsDashboard /></ProtectedRoute>
          } /> */}
          <Route path="/allocations/new" element={<ProtectedRoute><AllocationDashboard /></ProtectedRoute>} />
          {/* <Route path="/allocations/new" element={<ComplexAllocationDashboard />} /> */}
          <Route path="/allocations/:id" element={<AllocationView />} />
          <Route path = '/health' element= {<SupplyHealthDashboard/>} />
          <Route path="/dashboard" element={
            <ProtectedRoute><Dashboard /></ProtectedRoute>
          } />
          
          

          <Route path="*" element={<Navigate to="/dashboard" />} />
        </Routes>
      </BrowserRouter>
      </AuthProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;