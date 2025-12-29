import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import Dashboard from "./Dashboard";

import Login from "./Login";

import AllocationView from './AllocationView';
import AllocationDashboard from "./AllocationDashboard";

const queryClient = new QueryClient();

const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const token = localStorage.getItem('auth_token'); // Changed from 'token' to 'auth_token'
  
  if (!token) {
    console.log('⚠️ No token found, redirecting to login');
    return <Navigate to="/login" />;
  }
  
  console.log('✅ Token found, allowing access');
  return children;
};

// wrapper to read the route param and pass it to FarmerProfil

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter basename="/">
        <Routes>
          <Route path="/login" element={<Login />} />
          
   
          <Route path="/allocations/new" element={<ProtectedRoute><AllocationDashboard /></ProtectedRoute>} />
          {/* <Route path="/allocations/new" element={<ComplexAllocationDashboard />} /> */}
          <Route path="/allocations/:id" element={<AllocationView />} />
          
          <Route path="/dashboard" element={
            <ProtectedRoute><Dashboard /></ProtectedRoute>
          } />
          
          

          <Route path="*" element={<Navigate to="/dashboard" />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;