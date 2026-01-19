import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  ArrowLeft, Users, Truck, DollarSign, 
  FileText, ExternalLink, Car, XCircle, CheckCircle, Clock, 
  MapPin, Phone, TrendingUp, TrendingDown, AlertCircle, Layers
} from 'lucide-react';
import { getAuthConfig } from './utils/auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_SUPPLY;
const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

const AllocationView: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  
  // Single Allocation Data
  const [data, setData] = useState<any>(null);
  const [mukkadam, setMukkadam] = useState<any>(null);
  const [provider, setProvider] = useState<any>(null);
  
  // Full Job Context Data
  const [fullJob, setFullJob] = useState<any>(null);
  const [farmer, setFarmer] = useState<any>(null);
  const [jobActivity, setJobActivity] = useState<any>(null);
  
  const [loading, setLoading] = useState(true);
  const [mukkadamPaymentRequest, setMukkadamPaymentRequest] = useState<any>(null);
  const [transportPaymentRequest, setTransportPaymentRequest] = useState<any>(null);

  useEffect(() => {
    const fetchCoreData = async () => {
      const config = getAuthConfig();
      setLoading(true);

    //   const t = 'Token 307a2e56b1bb0e13c173ac0fabf6d05629dcd203'
    const t = 'Token b5920d610d85bff62bb0ab70f971ed6a44eb1b8c'

    const supply = '307a2e56b1bb0e13c173ac0fabf6d05629dcd203'

      try {
        // ✅ 1. PARALLEL FETCH: Get Allocation & Payments immediately
        const [allocationRes, mukkadamPayRes, transportPayRes] = await Promise.all([
          axios.get(`${API_BASE_URL_A}/ap/allocations/${id}/`, config),
          axios.get(`${API_BASE_URL_A}/ap/payment-requests/?allocation=${id}`, config),
          axios.get(`${API_BASE_URL_A}/ap/transport-payment-requests/?allocation=${id}`, config)
        ]);

        const currentAllocation = allocationRes.data;
        setData(currentAllocation);

        if (mukkadamPayRes.data.length > 0) setMukkadamPaymentRequest(mukkadamPayRes.data[0]);
        if (transportPayRes.data.length > 0) setTransportPaymentRequest(transportPayRes.data[0]);

        // ✅ 2. SECONDARY FETCH: Get Details (Mukkadam, Provider, Job) based on Allocation data
        // We start these requests immediately without waiting for each other
        const secondaryPromises = [];

        // Fetch Mukkadam
        secondaryPromises.push(
          axios.get(`${API_BASE_URL}/api/mukkadam/${currentAllocation.mukkadam_id}/`
            
          )
            .then(res => setMukkadam(res.data))
            .catch(err => console.error('Failed to fetch mukkadam', err))
        );

        // Fetch Provider (if exists)
        if (currentAllocation.transport_type === 'provider' && currentAllocation.transport_provider_id) {
          secondaryPromises.push(
             axios.get(`${API_BASE_URL}/api/transport-providers/${currentAllocation.transport_provider_id}/`, 
              { headers: { 'Authorization': `Token ${supply}` } }
             )
             .then(res => setProvider(res.data))
             .catch(err => console.error('Failed to fetch provider', err))
          );
        }

        // ✅ OPTIMIZED JOB FETCH
        // Instead of fetching ALL jobs, we try to fetch just the specific job context if your API supports it.
        // If your API DOES NOT support fetching a single job by ID, we have to filter.
        // Assuming you might add a endpoint like /ap/jobs/{id}/ in the future.
        // For now, we keep the filter logic but ensure it runs in parallel.
        
        // if (currentAllocation.farmer_work_id || currentAllocation.job_id) {
        //    const jobId = currentAllocation.farmer_work_id || currentAllocation.job_id;
           
        //    secondaryPromises.push(
        //      // ⚠️ PERFOMANCE NOTE: Ideally replace this with `${API_BASE_URL_A}/ap/jobs/${jobId}/`
        //      axios.get(`${API_BASE_URL_A}/ap/jobs/`, config) 
        //        .then(async (res) => {
        //           const job = res.data.find((j: any) => j.work_id === jobId);
        //           if (job) {
        //             setFullJob(job);
                    
        //             const activity = job.activities?.find((a: any) => a.activity_name === currentAllocation.activity_name);
        //             if (activity) setJobActivity(activity);

        //             // Fetch Farmer only after we have the job
        //             if (job.farmer_id) {
        //                const t = "e8fa8310c9af344ca22ec6bd23960d609b09c704";
        //                try {
        //                  const farmerRes = await axios.get(
        //                    `https://sahyadri.kisanmitra.ai/fir/api/get_farmer_details/${job.farmer_id}/`,
        //                    { headers: { 'Authorization': `Token ${t}` } }
        //                  );
        //                  setFarmer(farmerRes.data);
        //                } catch (e) { console.error('Farmer fetch error', e); }
        //             }
        //           }
        //        })
        //        .catch(err => console.error('Failed to fetch job context', err))
        //    );
        // }

        // 5. ✅ FETCH FULL JOB DETAILS (OPTIMIZED)
        const jobId = currentAllocation.farmer_work_id || currentAllocation.job_id;
        
        if (jobId) {
            try {
                // Call the NEW fast endpoint
                const jobRes = await axios.get(`${API_BASE_URL_A}/ap/job-details/${jobId}/`, config);
                const job = jobRes.data;

                // Enrich allocations with Mukkadam names from the cache/API
                // Since the local DB endpoint returns "Mukkadam #123", we can try to find names 
                // if we have them in a global store, or fetch them lazily. 
                // For now, even IDs are better than a 30s wait.
                
                setFullJob(job); 

                // Set local activity context
                const activity = job.activities?.find((a: any) => a.activity_name === currentAllocation.activity_name);
                if (activity) setJobActivity(activity);

                // 6. FETCH FARMER SEPARATELY (Since local DB doesn't have it)
                // We rely on the external farmer API only if we really need it.
                // Note: If you stored farmer_id in JobActivity model, this would be instant too.
                // For now, we skip or fetch if you have an endpoint for it.
                
            } catch (error) {
                console.error('Failed to fetch job details:', error);
            }
        }

        // Wait for all secondary data to load (or fail gracefully)
        await Promise.all(secondaryPromises);

      } catch (error) {
        console.error('Critical Error fetching allocation:', error);
        // navigate('/allocations'); // Optional: redirect on critical fail
      } finally {
        setLoading(false);
      }
    };

    if (id) {
        fetchCoreData();
    }
  }, [id, navigate]);

  if (loading || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading details...</p>
        </div>
      </div>
    );
  }

  // ... (Rest of your rendering logic remains EXACTLY the same) ...
  // --- CALCULATIONS FOR SINGLE ALLOCATION ---
  const currentCost = parseFloat(data.mukkadam_price || 0) + parseFloat(data.transport_price || 0);
  
  // --- CALCULATIONS FOR FULL JOB (All Allocations) ---
  let totalJobRevenue = 0;
  let totalJobCost = 0;
  let totalJobAllocationsCount = 0;

  if (fullJob && fullJob.activities) {
    fullJob.activities.forEach((act: any) => {
        totalJobRevenue += parseFloat(act.total_price || 0); 
        if (act.allocations) {
            act.allocations.forEach((alloc: any) => {
                totalJobAllocationsCount++;
                totalJobCost += parseFloat(alloc.mukkadam_price || 0) + parseFloat(alloc.transport_price || 0);
            });
        }
    });
  } else {
    totalJobCost = currentCost; 
    totalJobRevenue = jobActivity?.total_price || 0;
  }

  const jobProfit = totalJobRevenue - totalJobCost;
  const jobMargin = totalJobRevenue > 0 ? (jobProfit / totalJobRevenue) * 100 : 0;

  const getTransportDisplay = (allocData: any) => {
    if (allocData.transport_type === 'none') return { icon: XCircle, color: 'text-gray-500', text: 'None' };
    if (allocData.transport_type === 'own') return { icon: Car, color: 'text-blue-500', text: 'Own' };
    return { icon: Truck, color: 'text-orange-500', text: 'Provider' };
  };

  const currentTransport = getTransportDisplay(data);
  const TransportIcon = currentTransport.icon;

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Navigation */}
        <div className="flex justify-between items-center">
            <button onClick={() => navigate('/allocations')} className="flex items-center text-gray-600 hover:text-black transition">
            <ArrowLeft className="mr-2" size={20} /> Back to Dashboard
            </button>
            <span className="px-3 py-1 bg-gray-200 text-gray-700 rounded-full text-xs font-mono">
                Job ID: {fullJob?.work_id || data.farmer_work_id}
            </span>
        </div>

        {/* ✅ GLOBAL JOB HEADER (Aggregated Data) */}
        <div className="bg-white rounded-2xl shadow-lg overflow-hidden border-2 border-indigo-100">
          <div className="bg-gradient-to-r from-indigo-600 to-blue-600 px-8 py-6 text-white">
            <div className="flex justify-between items-start">
                <div>
                    <h1 className="text-2xl font-bold flex items-center">
                        <FileText className="mr-2" /> 
                        {fullJob?.title || `Job #${data.farmer_work_id}`}
                    </h1>
                    {farmer && (
                        <p className="mt-1 opacity-90 flex items-center text-indigo-100">
                            <Users size={16} className="mr-2" /> 
                            {farmer.farmer_name} • {farmer.village}
                        </p>
                    )}
                </div>
                <div className="text-right">
                    <p className="text-sm opacity-80">Total Job Profit</p>
                    <p className={`text-3xl font-bold ${jobProfit >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                        {jobProfit >= 0 ? '+' : ''}₹{jobProfit.toLocaleString()}
                    </p>
                    <p className="text-xs opacity-75">{jobMargin.toFixed(1)}% margin</p>
                </div>
            </div>
          </div>

          {/* Job Aggregate Stats */}
          <div className="grid grid-cols-4 divide-x divide-gray-100 border-b border-gray-100">
            <div className="p-4 text-center">
                <p className="text-xs text-gray-500 uppercase font-bold">Total Allocations</p>
                <p className="text-xl font-bold text-gray-800">{totalJobAllocationsCount}</p>
            </div>
            <div className="p-4 text-center">
                <p className="text-xs text-gray-500 uppercase font-bold">Total Revenue</p>
                <p className="text-xl font-bold text-green-600">₹{totalJobRevenue.toLocaleString()}</p>
            </div>
            <div className="p-4 text-center">
                <p className="text-xs text-gray-500 uppercase font-bold">Total Cost</p>
                <p className="text-xl font-bold text-red-500">₹{totalJobCost.toLocaleString()}</p>
            </div>
            <div className="p-4 text-center bg-gray-50">
                <p className="text-xs text-gray-500 uppercase font-bold">Current View</p>
                <p className="text-sm font-semibold text-blue-600">Allocation #{data.id}</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            
            {/* LEFT COLUMN: The Specific Allocation Viewed */}
            <div className="xl:col-span-2 space-y-6">
                
                {/* Specific Mukkadam & Activity Card */}
                <div className="bg-white rounded-xl shadow-lg border-l-4 border-blue-500 overflow-hidden">
                    <div className="p-6">
                        <div className="flex justify-between items-start mb-6">
                            <div>
                                <h3 className="text-lg font-bold text-gray-900 flex items-center">
                                    <Users className="mr-2 text-blue-500"/> 
                                    {mukkadam?.mukkadam_name || 'Loading Mukkadam...'}
                                </h3>
                                <p className="text-gray-500 text-sm">{mukkadam?.village} • {mukkadam?.mobile_numbers}</p>
                            </div>
                            <div className="text-right">
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-800">
                                    CURRENTLY VIEWING
                                </span>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                            <div>
                                <p className="text-xs text-gray-500 uppercase font-bold">Activity</p>
                                <p className="font-semibold text-gray-800">{data.activity_name}</p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-500 uppercase font-bold">Area Allocated</p>
                                <p className="font-semibold text-gray-800">{data.allocated_area} acres</p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-500 uppercase font-bold">Crew Size</p>
                                <p className="font-semibold text-teal-600 flex items-center">
                                    <Users size={14} className="mr-1"/> {data.crew_size || mukkadam?.crew_size}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-500 uppercase font-bold">Work Date</p>
                                <p className="font-semibold text-gray-800">
                                    {new Date(data.work_date).toLocaleDateString('en-IN')}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-500 uppercase font-bold">Allocated By</p>
                                <p className="font-semibold text-gray-800">
                                    {data.allocated_by?.username || 'System'}
                                </p>
                            </div>
                        </div>

                        {/* Payment Statuses for THIS allocation - ENHANCED */}
<div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-gray-100">
  {/* Mukkadam Payment */}
  <div className={`p-4 rounded-lg border-2 transition ${
    mukkadamPaymentRequest?.status === 'paid' 
      ? 'bg-green-50 border-green-300 shadow-sm' 
      : mukkadamPaymentRequest?.status === 'pending'
      ? 'bg-yellow-50 border-yellow-300'
      : 'bg-gray-50 border-gray-200'
  }`}>
    <div className="flex items-start justify-between mb-3">
      <p className="text-xs text-gray-500 uppercase font-bold flex items-center">
        <DollarSign size={14} className="mr-1" />
        Mukkadam Payment
      </p>
      {mukkadamPaymentRequest ? (
        <span className={`text-xs font-bold px-2 py-1 rounded-full flex items-center gap-1 ${
          mukkadamPaymentRequest.status === 'paid' 
            ? 'bg-green-200 text-green-800' 
            : mukkadamPaymentRequest.status === 'pending'
            ? 'bg-yellow-200 text-yellow-800'
            : 'bg-red-200 text-red-800'
        }`}>
          {mukkadamPaymentRequest.status === 'paid' && <CheckCircle size={12} />}
          {mukkadamPaymentRequest.status === 'pending' && <Clock size={12} />}
          {mukkadamPaymentRequest.status === 'rejected' && <XCircle size={12} />}
          {mukkadamPaymentRequest.status.toUpperCase()}
        </span>
      ) : (
        <span className="text-xs text-gray-400 italic">Not Requested</span>
      )}
    </div>
    
    <p className="text-2xl font-bold text-blue-600 mb-2">
      ₹{parseFloat(data.mukkadam_price).toLocaleString()}
    </p>
    
    {mukkadamPaymentRequest && (
      <div className="space-y-1 text-xs text-gray-600">
        {mukkadamPaymentRequest.requested_at && (
          <p>Requested: {new Date(mukkadamPaymentRequest.requested_at).toLocaleDateString('en-IN')}</p>
        )}
        {mukkadamPaymentRequest.paid_at && (
          <p className="text-green-600 font-semibold">
            Paid: {new Date(mukkadamPaymentRequest.paid_at).toLocaleDateString('en-IN')}
          </p>
        )}
      </div>
    )}
  </div>

  {/* Transport Payment */}
  <div className={`p-4 rounded-lg border-2 transition ${
    transportPaymentRequest?.status === 'paid' 
      ? 'bg-green-50 border-green-300 shadow-sm' 
      : transportPaymentRequest?.status === 'pending'
      ? 'bg-yellow-50 border-yellow-300'
      : 'bg-gray-50 border-gray-200'
  }`}>
    <div className="flex items-start justify-between mb-3">
      <p className="text-xs text-gray-500 uppercase font-bold flex items-center">
        <TransportIcon size={14} className={`mr-1 ${currentTransport.color}`} />
        {currentTransport.text} Transport
      </p>
      {transportPaymentRequest ? (
        <span className={`text-xs font-bold px-2 py-1 rounded-full flex items-center gap-1 ${
          transportPaymentRequest.status === 'paid' 
            ? 'bg-green-200 text-green-800' 
            : transportPaymentRequest.status === 'pending'
            ? 'bg-yellow-200 text-yellow-800'
            : 'bg-red-200 text-red-800'
        }`}>
          {transportPaymentRequest.status === 'paid' && <CheckCircle size={12} />}
          {transportPaymentRequest.status === 'pending' && <Clock size={12} />}
          {transportPaymentRequest.status === 'rejected' && <XCircle size={12} />}
          {transportPaymentRequest.status.toUpperCase()}
        </span>
      ) : (
        <span className="text-xs text-gray-400 italic">
          {data.transport_type === 'provider' ? 'Not Requested' : 'N/A'}
        </span>
      )}
    </div>
    
    <p className="text-2xl font-bold text-orange-600 mb-2">
      ₹{parseFloat(data.transport_price || 0).toLocaleString()}
    </p>
    
    {data.transport_type === 'provider' && provider && (
      <p className="text-xs text-gray-600 font-semibold">{provider.name}</p>
    )}
    
    {transportPaymentRequest && (
      <div className="space-y-1 text-xs text-gray-600 mt-2">
        {transportPaymentRequest.requested_at && (
          <p>Requested: {new Date(transportPaymentRequest.requested_at).toLocaleDateString('en-IN')}</p>
        )}
        {transportPaymentRequest.paid_at && (
          <p className="text-green-600 font-semibold">
            Paid: {new Date(transportPaymentRequest.paid_at).toLocaleDateString('en-IN')}
          </p>
        )}
      </div>
    )}
  </div>
</div>
                    </div>
                </div>


{/* Transport Provider Details Card - ADD THIS NEW SECTION */}
{data.transport_type === 'provider' && provider && (
  <div className="bg-white rounded-xl shadow-lg border-l-4 border-orange-500 overflow-hidden">
    <div className="p-6">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h3 className="text-lg font-bold text-gray-900 flex items-center">
            <Truck className="mr-2 text-orange-500"/> 
            {provider.name}
          </h3>
          <p className="text-gray-500 text-sm flex items-center mt-1">
            <MapPin size={14} className="mr-1" />
            {provider.base_location || provider.district || 'Location not specified'}
          </p>
        </div>
        <div className="text-right">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-orange-100 text-orange-800">
            TRANSPORT PROVIDER
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
        {/* Contact Number */}
        <div>
          <p className="text-xs text-gray-500 uppercase font-bold">Contact</p>
          <p className="font-semibold text-gray-800 flex items-center">
            <Phone size={14} className="mr-1 text-gray-400"/>
            {provider.contact_number || 'Not provided'}
          </p>
        </div>

        {/* Vehicle Type */}
        <div>
          <p className="text-xs text-gray-500 uppercase font-bold">Vehicle Type</p>
          <p className="font-semibold text-gray-800">
            {provider.vehicle_type || 'Not specified'}
          </p>
        </div>

        {/* Max Distance */}
        <div>
          <p className="text-xs text-gray-500 uppercase font-bold">Service Range</p>
          <p className="font-semibold text-teal-600">
            {provider.max_distance ? `${provider.max_distance} km` : 'Any distance'}
          </p>
        </div>

        {/* Location Details */}
        {provider.district && (
          <div>
            <p className="text-xs text-gray-500 uppercase font-bold">District</p>
            <p className="font-semibold text-gray-800">{provider.district}</p>
          </div>
        )}

        {provider.taluka && (
          <div>
            <p className="text-xs text-gray-500 uppercase font-bold">Taluka</p>
            <p className="font-semibold text-gray-800">{provider.taluka}</p>
          </div>
        )}

        {/* Status */}
        <div>
          <p className="text-xs text-gray-500 uppercase font-bold">Status</p>
          <p className="font-semibold">
            {provider.is_active ? (
              <span className="flex items-center text-green-600">
                <CheckCircle size={14} className="mr-1" />
                Active
              </span>
            ) : (
              <span className="flex items-center text-gray-400">
                <XCircle size={14} className="mr-1" />
                Inactive
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Transport Price Breakdown */}
      <div className="mt-6 pt-4 border-t border-gray-100">
        <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-xs text-gray-500 uppercase font-bold mb-1">Transport Charges</p>
              <p className="text-2xl font-bold text-orange-600">
                ₹{parseFloat(data.transport_price || 0).toLocaleString()}
              </p>
            </div>
            <div className="text-right">
              {transportPaymentRequest ? (
                <div>
                  <span className={`text-xs font-bold px-3 py-1 rounded-full ${
                    transportPaymentRequest.status === 'paid' 
                      ? 'bg-green-200 text-green-800' 
                      : transportPaymentRequest.status === 'pending'
                      ? 'bg-yellow-200 text-yellow-800'
                      : 'bg-red-200 text-red-800'
                  }`}>
                    {transportPaymentRequest.status.toUpperCase()}
                  </span>
                  {transportPaymentRequest.paid_at && (
                    <p className="text-xs text-gray-500 mt-1">
                      Paid: {new Date(transportPaymentRequest.paid_at).toLocaleDateString('en-IN')}
                    </p>
                  )}
                  {transportPaymentRequest.paid_by && (
                    <p className="text-xs text-gray-600 mt-1">
                      By: {transportPaymentRequest.paid_by.username}
                    </p>
                  )}
                </div>
              ) : (
                <span className="text-xs text-gray-400 italic">Payment Not Requested</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Additional Notes */}
      {provider.notes && (
        <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
          <p className="text-xs text-gray-500 uppercase font-bold mb-1">Provider Notes</p>
          <p className="text-sm text-gray-700">{provider.notes}</p>
        </div>
      )}

      {/* Allocation Details */}
      <div className="mt-4 pt-4 border-t border-gray-100">
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <p className="text-gray-500 uppercase font-bold">Allocated By</p>
            <p className="font-semibold text-gray-800 mt-1">
              {data.allocated_by?.username || 'System'}
            </p>
          </div>
          <div>
            <p className="text-gray-500 uppercase font-bold">Allocation Date</p>
            <p className="font-semibold text-gray-800 mt-1">
              {new Date(data.created_at || data.work_date).toLocaleDateString('en-IN', {
                day: '2-digit',
                month: 'short',
                year: 'numeric'
              })}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
)}

{/* Own Transport Info Card */}
{data.transport_type === 'own' && (
  <div className="bg-white rounded-xl shadow-lg border-l-4 border-blue-500 overflow-hidden">
    <div className="p-6">
      <div className="flex items-start space-x-4">
        <div className="bg-blue-100 p-4 rounded-lg">
          <Car className="w-8 h-8 text-blue-600" />
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-bold text-gray-900 mb-2">
            Own Transport Arrangement
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            The mukkadam is using their own transport for this allocation.
          </p>
          
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-xs text-gray-500 uppercase font-bold mb-1">Transport Charges</p>
                <p className="text-2xl font-bold text-blue-600">
                  ₹{parseFloat(data.transport_price || 0).toLocaleString()}
                </p>
              </div>
              {mukkadam?.transport_mode && (
                <div className="text-right">
                  <p className="text-xs text-gray-500 uppercase font-bold mb-1">Vehicle Type</p>
                  <p className="text-sm font-semibold text-gray-700">
                    {mukkadam.transport_mode.replace(/_/g, ' ').replace('own ', '')}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
)}

{/* No Transport Card */}
{data.transport_type === 'none' && (
  <div className="bg-white rounded-xl shadow-lg border-l-4 border-gray-400 overflow-hidden">
    <div className="p-6">
      <div className="flex items-center space-x-4">
        <div className="bg-gray-100 p-4 rounded-lg">
          <XCircle className="w-8 h-8 text-gray-600" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-gray-900 mb-1">
            No Transport Required
          </h3>
          <p className="text-sm text-gray-600">
            Local workforce - No transportation arranged for this allocation.
          </p>
        </div>
      </div>
    </div>
  </div>
)}
                {/* Farmer Details (Compact) */}
                {farmer && (
                    <div className="bg-white p-6 rounded-xl shadow-lg border-l-4 border-indigo-500">
                        <h3 className="text-lg font-bold text-gray-800 mb-4">Farmer Information</h3>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <p className="text-xs text-gray-500 uppercase font-bold">Name</p>
                                <p className="text-gray-900">{farmer.farmer_name}</p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-500 uppercase font-bold">Location</p>
                                <p className="text-gray-900">{farmer.village}, {farmer.taluka}</p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-500 uppercase font-bold">Contact</p>
                                <p className="text-gray-900">{farmer.phone_number}</p>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* RIGHT COLUMN: Full Job Breakdown (The new requirement) */}
            <div className="bg-gray-50 rounded-xl shadow-inner border border-gray-200 p-4 h-fit">
                <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                    <Layers className="mr-2 text-indigo-600" />
                    Full Job Breakdown
                </h3>
                
                {fullJob?.activities ? (
                    <div className="space-y-6">
                        {fullJob.activities.map((activity: any, idx: number) => {
                            const hasAllocations = activity.allocations && activity.allocations.length > 0;
                            return (
                                <div key={idx} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                                    <div className="bg-gray-100 px-4 py-2 border-b border-gray-200 flex justify-between items-center">
                                        <span className="font-bold text-gray-700 text-sm">{activity.activity_name}</span>
                                        <span className="text-xs bg-gray-200 px-2 py-1 rounded text-gray-600">
                                            {activity.total_area} acres
                                        </span>
                                    </div>
                                    
                                    {!hasAllocations ? (
                                        <div className="p-4 text-center text-gray-400 text-xs italic">
                                            No allocations for this activity yet.
                                        </div>
                                    ) : (
                                        <div className="divide-y divide-gray-100">
                                            {activity.allocations.map((alloc: any) => {
                                                const isCurrent = alloc.allocation_id === parseInt(id || '0'); // Highlight current
                                                return (
                                                    <div 
                                                        key={alloc.allocation_id} 
                                                        onClick={() => !isCurrent && navigate(`/allocations/${alloc.allocation_id}`)}
                                                        className={`p-3 transition cursor-pointer ${
                                                            isCurrent ? 'bg-blue-50 border-l-4 border-blue-500' : 'hover:bg-gray-50'
                                                        }`}
                                                    >
                                                        <div className="flex justify-between items-start">
                                                            <div>
                                                                <p className={`text-sm font-semibold ${isCurrent ? 'text-blue-700' : 'text-gray-800'}`}>
                                                                    {alloc.mukkadam_name}
                                                                </p>
                                                                <p className="text-xs text-gray-500">
                                                                    {alloc.allocated_area} acres • {alloc.crew_size || '?'} crew
                                                                </p>
                                                            </div>
                                                            <div className="text-right">
                                                                <p className="text-sm font-bold text-gray-700">
                                                                    ₹{((alloc.mukkadam_price || 0) + (alloc.transport_price || 0)).toLocaleString()}
                                                                </p>
                                                                {isCurrent && (
                                                                    <span className="text-[10px] uppercase font-bold text-blue-500">Viewing</span>
                                                                )}
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="text-center py-8 text-gray-500">
                        {/* We hide loading here because the main spinner handles it, this is just empty state */}
                        {loading ? 'Loading context...' : 'Loading full job context...'}
                    </div>
                )}
            </div>

        </div>
      </div>
    </div>
  );
};

export default AllocationView;