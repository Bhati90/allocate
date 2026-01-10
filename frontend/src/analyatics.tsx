import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom'; // Added for routing
import axios from 'axios';
import { 
  Users, Calendar, DollarSign, TrendingUp, 
  CheckCircle, Clock, ArrowRight, Phone, MapPin, ArrowLeft 
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

const MukkadamPerformanceDashboard = () => {
  const { id } = useParams(); // Get ID from /analyatics/:id
  const navigate = useNavigate();
  
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('completed');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem('auth_token');
        
        // Calling your "Super API" on the Allocation Side
        const response = await axios.get(`${API_BASE}/ap/dashboard/`, { 
          params: { mukkadam_id: id },
          headers: { Authorization: `Token ${token}` }
        });
        
        setData(response.data);
      } catch (err) {
        console.error("Error fetching analytics:", err);
        // Optional: navigate back if mukkadam not found
        // alert("Mukkadam not found");
        // navigate('/dashboard');
      } finally {
        setLoading(false);
      }
    };

    if (id) fetchData();
  }, [id]);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
            <p className="mt-4 text-gray-500 font-medium">Crunching Performance Data...</p>
        </div>
    </div>
  );
  
  if (!data) return <div className="p-10 text-center text-red-500">Mukkadam data not found.</div>;

  const { mukkadam, financial_summary, work_history, recent_activity } = data;

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-8 space-y-6 bg-gray-50 min-h-screen">
      
      {/* Navigation Header */}
      <div className="flex justify-between items-center mb-2">
        <button 
          onClick={() => navigate(-1)} 
          className="flex items-center text-gray-500 hover:text-indigo-600 transition font-medium"
        >
          <ArrowLeft size={20} className="mr-2"/> Back
        </button>
        <div className="text-xs font-bold text-gray-400 uppercase tracking-widest">
            Mukkadam Analytics Engine v1.0
        </div>
      </div>

      {/* 1. Profile & Utilization Header */}
      <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-6 flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="flex items-center gap-5">
          <div className="h-20 w-20 bg-gradient-to-br from-indigo-600 to-blue-500 rounded-2xl flex items-center justify-center text-white text-3xl font-bold shadow-lg shadow-indigo-100">
            {mukkadam.info.mukkadam_name[0]}
          </div>
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900">{mukkadam.info.mukkadam_name}</h1>
            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 mt-2">
              <span className="flex items-center bg-gray-100 px-3 py-1 rounded-full">
                <Phone size={14} className="mr-2 text-indigo-500"/> {mukkadam.info.mobile_numbers}
              </span>
              <span className="flex items-center bg-gray-100 px-3 py-1 rounded-full">
                <MapPin size={14} className="mr-2 text-indigo-500"/> {mukkadam.info.village}
              </span>
              {mukkadam.is_active && (
                <span className="bg-green-500 text-white px-3 py-1 rounded-full text-[10px] font-black uppercase">Active</span>
              )}
            </div>
          </div>
        </div>
        
        {/* Work Utilization Meter */}
        <div className="bg-indigo-50 p-5 rounded-2xl border border-indigo-100 w-full md:w-72">
          <div className="flex justify-between items-end mb-2">
            <p className="text-xs text-indigo-600 font-black uppercase">Efficiency</p>
            <span className="text-2xl font-black text-indigo-700">{mukkadam.utilization.utilization_rate}%</span>
          </div>
          <div className="w-full bg-indigo-200 h-3 rounded-full overflow-hidden">
            <div 
                className="bg-indigo-600 h-full transition-all duration-1000 ease-out" 
                style={{ width: `${mukkadam.utilization.utilization_rate}%` }}
            ></div>
          </div>
          <p className="text-[10px] text-indigo-400 mt-2 font-bold text-center italic">
            {mukkadam.utilization.worked_days} days worked out of {mukkadam.utilization.available_days} available
          </p>
        </div>
      </div>

      {/* 2. Financial Summary Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Potential" value={financial_summary.total_earning_potential} icon={<TrendingUp size={20}/>} theme="blue" />
        <StatCard title="Received" value={financial_summary.total_received} icon={<CheckCircle size={20}/>} theme="green" />
        <StatCard title="Pending" value={financial_summary.pending_from_completed} icon={<Clock size={20}/>} theme="orange" />
        <StatCard title="Upcoming" value={financial_summary.upcoming_projected} icon={<Calendar size={20}/>} theme="purple" />
      </div>

      {/* 3. Main Split View: History vs Changes */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left: Work History Tabs */}
        <div className="lg:col-span-2 bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="flex bg-gray-50 border-b">
            {['completed', 'pending', 'upcoming'].map((tab) => (
              <button 
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 py-4 text-xs font-black uppercase tracking-tighter transition-all ${
                    activeTab === tab 
                    ? 'bg-white text-indigo-700 border-t-4 border-indigo-600 shadow-sm' 
                    : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                }`}
              >
                {tab} ({work_history[tab]?.length || 0})
              </button>
            ))}
          </div>
          
          <div className="p-6 space-y-4 max-h-[600px] overflow-y-auto">
            {(!work_history[activeTab] || work_history[activeTab].length === 0) ? (
              <div className="py-20 text-center">
                  <div className="text-4xl mb-2">🏜️</div>
                  <p className="text-gray-400 font-medium">No records for {activeTab} jobs.</p>
              </div>
            ) : (
              work_history[activeTab].map((job) => (
                <div key={job.id} className="group relative bg-white border border-gray-100 rounded-2xl p-5 hover:border-indigo-400 hover:shadow-md transition-all duration-300">
                  <div className="flex justify-between items-start">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded uppercase">{job.date}</span>
                        <span className="text-[10px] font-bold text-gray-400 uppercase">#{job.id}</span>
                      </div>
                      <h3 className="font-extrabold text-gray-900 text-lg leading-tight group-hover:text-indigo-600 transition-colors">{job.job_name}</h3>
                      <p className="text-sm text-gray-500 font-medium italic">Farmer: {job.farmer_name}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xl font-black text-gray-900">₹{job.total_cost.toLocaleString()}</p>
                      <p className="text-[11px] font-bold text-gray-400 mt-1">{job.area} ACRES ALLOCATED</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right: Change Log / Audit Trail */}
        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-6 flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-black text-gray-800 flex items-center gap-2 text-sm uppercase tracking-widest">
                <Clock size={18} className="text-indigo-600"/> Audit Log
            </h2>
          </div>
          
          <div className="space-y-6 overflow-y-auto pr-2 custom-scrollbar">
            {recent_activity.map((log, idx) => (
              <div key={idx} className="relative pl-7 border-l-2 border-dashed border-indigo-100 pb-1 last:pb-0">
                {/* Dot */}
                <div className="absolute -left-[7px] top-0 h-3 w-3 bg-indigo-600 rounded-full ring-4 ring-indigo-50"></div>
                
                <p className="text-[9px] font-black text-indigo-400 uppercase leading-none mb-2 tracking-tighter">
                    {new Date(log.time).toLocaleString([], { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' })}
                </p>
                
                <h4 className="text-xs font-black text-gray-800 leading-tight uppercase">{log.type}</h4>
                <p className="text-[11px] text-gray-500 mt-1 leading-relaxed">{log.desc}</p>
                
                {/* Change Difference Visualizer */}
                {log.changes && Object.keys(log.changes).length > 0 && (
                  <div className="mt-3 bg-gray-50 rounded-xl p-3 border border-gray-100 space-y-2">
                    {Object.entries(log.changes).map(([field, values]) => (
                      <div key={field} className="flex flex-col gap-1">
                        <span className="text-[9px] font-black text-gray-400 uppercase tracking-widest">{field}</span>
                        <div className="flex items-center gap-2 text-[10px] font-bold">
                            <span className="text-red-400 line-through bg-red-50 px-1 rounded">{values.old}</span>
                            <ArrowRight size={10} className="text-indigo-300"/>
                            <span className="text-green-600 bg-green-50 px-1 rounded">{values.new}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                
                <p className="text-[9px] text-gray-400 mt-3 font-bold uppercase italic tracking-widest">
                    Authored by {log.user}
                </p>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
};

/**
 * Reusable Stat Card with Dynamic Themes
 */
const StatCard = ({ title, value, icon, theme }) => {
    const themes = {
        blue: "bg-blue-50 text-blue-600 border-blue-100",
        green: "bg-green-50 text-green-600 border-green-100",
        orange: "bg-orange-50 text-orange-600 border-orange-100",
        purple: "bg-purple-50 text-purple-600 border-purple-100",
    };

    return (
        <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 group hover:scale-[1.02] transition-transform duration-300">
            <div className="flex justify-between items-start">
                <div className={`p-3 rounded-2xl ${themes[theme]} mb-4`}>
                    {icon}
                </div>
            </div>
            <div>
                <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">{title}</p>
                <p className="text-2xl font-black text-gray-900 group-hover:text-indigo-600 transition-colors">
                    ₹{Number(value).toLocaleString()}
                </p>
            </div>
        </div>
    );
};

export default MukkadamPerformanceDashboard;