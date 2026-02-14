import React from 'react';
import { useNavigate } from 'react-router-dom';
import { UserPlus,MapPin, List,Truck, Calendar, UserCog, LogOut, FileText } from 'lucide-react';

import { useAuth } from './context/auth';
const Dashboard = () => {
  const navigate = useNavigate();
  
  const logout = () => {
    localStorage.clear();
    navigate('/loginf');
  };

  

const { isAdmin, userData, logout: authLogout, isLoading } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800">Agent Dashboard</h1>
        <button onClick={logout} className="flex items-center text-red-600 font-medium">
          <LogOut size={20} className="mr-2" /> Logout
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
        

        <button onClick={() => navigate('/allocations/new')} className="bg-orange-500 text-white p-8 rounded-xl shadow-lg flex flex-col items-center hover:bg-orange-600 transition">
          <UserCog size={48} className="mb-4" />
          <span className="text-2xl font-bold">Allocation</span>
        </button>

        {isAdmin && (
            <button 
              onClick={() => navigate('/analyatics')} 
              className="bg-gradient-to-br from-emerald-500 to-emerald-600 text-white p-8 rounded-xl shadow-lg flex flex-col items-center hover:from-emerald-600 hover:to-emerald-700 transition transform hover:scale-105"
            >
              <MapPin size={48} className="mb-4" />
              <span className="text-2xl font-bold">analytics</span>
              <span className="text-sm mt-2 opacity-90">Track analytics</span>
            </button>
          )}



          {isAdmin && (
            <button 
              onClick={() => navigate('/calls')} 
              className="bg-gradient-to-br from-emerald-500 to-emerald-600 text-white p-8 rounded-xl shadow-lg flex flex-col items-center hover:from-emerald-600 hover:to-emerald-700 transition transform hover:scale-105"
            >
              <MapPin size={48} className="mb-4" />
              <span className="text-2xl font-bold">calls</span>
              <span className="text-sm mt-2 opacity-90">Track calls</span>
            </button>
          )}
      </div>
    </div>
  );
};
export default Dashboard;