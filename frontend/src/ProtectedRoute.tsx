// src/components/ProtectedRoute.tsx
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './context/auth';

const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const { isLoading } = useAuth();
  const token = localStorage.getItem('auth_token');
  
  // ✅ Show loading while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Verifying authentication...</p>
        </div>
      </div>
    );
  }
  
  // ✅ Redirect if no token
  if (!token) {
    console.log('⚠️ No token found, redirecting to login');
    return <Navigate to="/loginf" replace />;
  }
  
  console.log('✅ Token verified, allowing access');
  return children;
};

export default ProtectedRoute;