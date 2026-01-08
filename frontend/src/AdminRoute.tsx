// src/components/AdminRoute.tsx
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './context/auth';
import { AlertCircle } from 'lucide-react';

const AdminRoute = ({ children }: { children: JSX.Element }) => {
  const { isAdmin, isLoading } = useAuth();
  const token = localStorage.getItem('auth_token');

  // ✅ Show loading while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Verifying admin permissions...</p>
        </div>
      </div>
    );
  }

  // ✅ Must be logged in
  if (!token) {
    console.log('❌ No token - redirecting to login');
    return <Navigate to="/login" replace />;
  }

  // ✅ Must be Admin
  if (!isAdmin) {
    console.log('❌ Not admin - access denied');
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md p-8 bg-white rounded-lg shadow-lg text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Access Denied</h2>
          <p className="text-gray-600 mb-6">You don't have permission to access this page.</p>
          <button 
            onClick={() => window.history.back()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return children;
};

export default AdminRoute;