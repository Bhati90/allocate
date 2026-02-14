import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { 
  Music, Phone, Calendar, Clock, Download, 
  Search, AlertCircle, RefreshCcw, PlayCircle, 
  CheckCircle2, XCircle, PhoneIncoming, PhoneOutgoing 
} from 'lucide-react';
import { getAuthConfig } from './utils/auth';

// Adjust based on your environment variables
const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

interface CallLog {
  id: number;
  call_sid: string;
  mobile_number: string;
  status: string;
  purpose: string;
  initiated_at: string;
  duration: number | null;
  audio_url: string | null;
  s3_key: string | null;
}

const CallsPage: React.FC = () => {
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');

  const fetchCalls = async (mobile?: string) => {
    setLoading(true);
    const config = getAuthConfig();
    try {
      const url = mobile 
        ? `${API_BASE_URL_A}/ap/farmer-calls/?mobile_number=${mobile}` 
        : `${API_BASE_URL_A}/ap/farmer-calls/`;
      
      const response = await axios.get(url, config);
      // Handle both paginated and list responses
      setCalls(Array.isArray(response.data) ? response.data : response.data.results || []);
    } catch (error) {
      console.error("Failed to fetch call recordings", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCalls();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchCalls(searchTerm);
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed': return 'bg-green-100 text-green-700 border-green-200';
      case 'failed': return 'bg-red-100 text-red-700 border-red-200';
      case 'no-answer': return 'bg-amber-100 text-amber-700 border-amber-200';
      default: return 'bg-blue-100 text-blue-700 border-blue-200';
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-black text-slate-900 flex items-center gap-3">
              <div className="bg-rose-500 p-2 rounded-lg text-white">
                <Music size={24} />
              </div>
              Communication Hub
            </h1>
            <p className="text-slate-500 mt-1 font-medium">Exotel Call Recordings & Interaction Logs</p>
          </div>

          <div className="flex flex-wrap gap-2 w-full md:w-auto">
            <form onSubmit={handleSearch} className="relative flex-1 md:flex-initial">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input 
                type="text"
                placeholder="Search mobile number..."
                className="pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl shadow-sm focus:ring-2 focus:ring-rose-500 outline-none w-full md:w-72 transition-all"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </form>
            <button 
              onClick={() => fetchCalls()} 
              className="p-2.5 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 shadow-sm transition-colors text-slate-600"
            >
              <RefreshCcw size={20} />
            </button>
          </div>
        </div>

        {/* List Section */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 bg-white rounded-3xl border border-slate-100 shadow-sm">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-500 mb-4"></div>
            <p className="text-slate-500 font-bold animate-pulse">Syncing Recordings...</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {calls.length > 0 ? (
              calls.map((call) => (
                <div key={call.id} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-rose-200 transition-all group">
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                    
                    {/* Call Meta */}
                    <div className="flex items-start gap-4">
                      <div className={`p-3 rounded-xl ${getStatusColor(call.status)} border shadow-sm`}>
                         {call.status === 'completed' ? <CheckCircle2 size={24} /> : <PhoneOutgoing size={24} />}
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-3">
                          <span className="text-xl font-bold text-slate-800 tracking-tight">{call.mobile_number}</span>
                          <span className={`text-[10px] uppercase font-black px-2 py-0.5 rounded-md border ${getStatusColor(call.status)}`}>
                            {call.status}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500 font-medium">
                          <div className="flex items-center gap-1.5"><Calendar size={14} className="text-slate-400" /> {new Date(call.initiated_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
                          <div className="flex items-center gap-1.5"><Clock size={14} className="text-slate-400" /> {call.duration || 0}s duration</div>
                          <div className="flex items-center gap-1.5 capitalize"><Phone size={14} className="text-slate-400" /> {call.purpose.replace('_', ' ')}</div>
                        </div>
                      </div>
                    </div>

                    {/* Audio Controls */}
                    <div className="flex items-center gap-3 bg-slate-50 p-3 rounded-2xl border border-slate-100 group-hover:bg-rose-50 transition-colors">
                      {call.audio_url ? (
                        <>
                          <audio 
                            src={call.audio_url} 
                            controls 
                            className="h-10 w-full md:w-64 accent-rose-500"
                          />
                          <a 
                            href={call.audio_url} 
                            target="_blank" 
                            rel="noreferrer"
                            className="p-2 text-slate-400 hover:text-rose-600 hover:bg-white rounded-lg transition-all"
                            title="Download Audio"
                          >
                            <Download size={20} />
                          </a>
                        </>
                      ) : (
                        <div className="flex items-center gap-2 text-slate-400 text-sm px-6 py-2">
                          <AlertCircle size={18} />
                          <span className="font-semibold">Processing Recording...</span>
                        </div>
                      )}
                    </div>

                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-24 bg-white border-2 border-dashed border-slate-200 rounded-3xl shadow-inner">
                <div className="bg-slate-50 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4 border border-slate-100">
                  <PlayCircle size={40} className="text-slate-300" />
                </div>
                <h3 className="text-slate-900 font-bold text-lg">No Recordings Found</h3>
                <p className="text-slate-400 max-w-xs mx-auto text-sm mt-1">Calls made via Exotel will automatically sync and appear here with audio links.</p>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
};

export default CallsPage;