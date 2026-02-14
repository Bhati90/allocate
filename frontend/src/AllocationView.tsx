import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  ArrowLeft, Users, Truck, DollarSign, 
  FileText, Car, XCircle, CheckCircle, Clock, 
  MapPin, Phone, AlertCircle, Layers
} from 'lucide-react';
import { getAuthConfig } from './utils/auth';

const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

const AllocationView: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  
  // Single Allocation Data (from new API)
  const [data, setData] = useState<any>(null);
  
  // Full Job Context Data (from new API)
  const [fullJob, setFullJob] = useState<any>(null);
  const [jobActivity, setJobActivity] = useState<any>(null);
  
  // Payment data
  const [mukkadamPaymentRequest, setMukkadamPaymentRequest] = useState<any>(null);
  const [transportPaymentRequest, setTransportPaymentRequest] = useState<any>(null);
  
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCoreData = async () => {
      const config = getAuthConfig();
      setLoading(true);

      try {
        // ✅ 1. Fetch allocation data
        const allocationRes = await axios.get(`${API_BASE_URL_A}/ap/allocations/${id}/`, config);
        const currentAllocation = allocationRes.data;
        setData(currentAllocation);

        // ✅ 2. Fetch payment requests
        const [mukkadamPayRes, transportPayRes] = await Promise.all([
          axios.get(`${API_BASE_URL_A}/ap/payment-requests/?allocation=${id}`, config),
          axios.get(`${API_BASE_URL_A}/ap/transport-payment-requests/?allocation=${id}`, config)
        ]);

        if (mukkadamPayRes.data.length > 0) setMukkadamPaymentRequest(mukkadamPayRes.data[0]);
        if (transportPayRes.data.length > 0) setTransportPaymentRequest(transportPayRes.data[0]);

        // ✅ 3. Fetch full job details (includes ALL data: farmer, mukkadam, transporter, payments)
        const jobId = currentAllocation.farmer_work_id || currentAllocation.job_id;
        
        if (jobId) {
          const jobRes = await axios.get(`${API_BASE_URL_A}/ap/job-details/${jobId}/`, config);
          const job = jobRes.data;
          setFullJob(job);

          // Find current activity context
          const activity = job.activities?.find((a: any) => 
            a.activity_name === currentAllocation.activity_name
          );
          if (activity) setJobActivity(activity);
        }

      } catch (error) {
        console.error('Critical Error fetching allocation:', error);
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

  // ✅ Get mukkadam details from fullJob data (not external API)
  const currentAllocationData = fullJob?.activities
    ?.flatMap((act: any) => act.allocations || [])
    ?.find((alloc: any) => alloc.allocation_id === parseInt(id || '0'));

  const mukkadamName = currentAllocationData?.mukkadam_name || `Mukkadam #${data.mukkadam_id}`;
  const transporterName = currentAllocationData?.transporter_name || null;

  // ✅ Get farmer details from fullJob
  const farmer = fullJob?.farmer;

  // --- CALCULATIONS FOR SINGLE ALLOCATION ---
  const currentCost = parseFloat(data.mukkadam_price || 0) + parseFloat(data.transport_price || 0);
  
  // --- CALCULATIONS FOR FULL JOB (All Allocations) ---
  let totalJobRevenue = 0;
  let totalJobCost = 0;
  let totalJobAllocationsCount = 0;
const total = Number(jobActivity?.total_price ?? 0);
const transport = Number(jobActivity?.transport_cost ?? 0);
const other = Number(jobActivity?.other_cost ?? 0);

const netAmount = total - transport - other;

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

  // ✅ Get farmer payment summary for current activity
  const farmerPaymentSummary = jobActivity?.farmer_payments;
  const farmerPayments = farmerPaymentSummary?.payments || [];

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
                    {farmer.farmer_name} • {farmer.location}
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
            

{/* Farmer's Payment Breakdown for Activity */}
<div className="bg-white p-6 rounded-xl shadow-lg border-l-4 border-green-500">
  <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center">
    <DollarSign className="mr-2 text-green-500" />
    Farmer's Payment Breakdown
  </h3>
  
  <div className="space-y-3">
    {/* Mukkadam Payment */}
    <div className="flex justify-between items-center pb-2 border-b border-gray-200">
      <div className="flex items-center">
        <Users size={16} className="mr-2 text-blue-500" />
        <span className="text-sm text-gray-600">For Mukkadam (Labour)</span>
      </div>
      <span className="text-lg font-bold text-blue-600">
        ₹{netAmount.toLocaleString('en-IN')}

      </span>
    </div>

    {/* Transport Payment */}
    <div className="flex justify-between items-center pb-2 border-b border-gray-200">
      <div className="flex items-center">
        <Truck size={16} className="mr-2 text-orange-500" />
        <span className="text-sm text-gray-600">For Transporter</span>
      </div>
      <span className="text-lg font-bold text-orange-600">
        ₹{parseFloat(jobActivity?.transport_cost || 0).toLocaleString()}
      </span>
    </div>

    {/* Other Costs */}
    <div className="flex justify-between items-center pb-2 border-b border-gray-200">
      <div className="flex items-center">
        <FileText size={16} className="mr-2 text-purple-500" />
        <span className="text-sm text-gray-600">Other Costs</span>
      </div>
      <span className="text-lg font-bold text-purple-600">
        ₹{parseFloat(jobActivity?.other_cost || 0).toLocaleString()}
      </span>
    </div>

    {/* Total */}
    <div className="flex justify-between items-center pt-2 bg-green-50 p-3 rounded-lg">
      <span className="text-sm font-bold text-gray-800 uppercase">
        Total Farmer Pays
      </span>
      <span className="text-2xl font-bold text-green-600">
        ₹{(
          parseFloat(jobActivity?.total_price || 0) 
        ).toLocaleString()}
      </span>
    </div>
  </div>
</div>
            
            {/* Specific Mukkadam & Activity Card */}
            <div className="bg-white rounded-xl shadow-lg border-l-4 border-blue-500 overflow-hidden">
              <div className="p-6">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h3 className="text-lg font-bold text-gray-900 flex items-center">
                      <Users className="mr-2 text-blue-500"/> 
                      {mukkadamName}
                    </h3>
                    {currentAllocationData?.labour_poc && (
                      <p className="text-gray-500 text-sm">Labour POC: {currentAllocationData.labour_poc}</p>
                    )}
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
                      <Users size={14} className="mr-1"/> {data.crew_size || 'N/A'}
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
                      {currentAllocationData?.allocated_by || 'System'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase font-bold">Status</p>
                    <p className="font-semibold text-gray-800 capitalize">
                      {data.status || 'allocated'}
                    </p>
                  </div>
                </div>

                {/* Payment Statuses - 3 COLUMNS */}
                <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-100">
                  
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
                    
                    {transporterName && (
                      <p className="text-xs text-gray-600 font-semibold">{transporterName}</p>
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

                  {/* Farmer Payment Card */}
                  <div className={`p-4 rounded-lg border-2 transition ${
                    farmerPaymentSummary?.pending_count === 0 && farmerPaymentSummary?.paid_count > 0
                      ? 'bg-green-50 border-green-300 shadow-sm' 
                      : farmerPaymentSummary?.pending_count > 0
                      ? 'bg-yellow-50 border-yellow-300'
                      : 'bg-gray-50 border-gray-200'
                  }`}>
                    <div className="flex items-start justify-between mb-3">
                      <p className="text-xs text-gray-500 uppercase font-bold flex items-center">
                        <Users size={14} className="mr-1" />
                        Farmer Payment
                      </p>
                      {farmerPaymentSummary ? (
                        <span className={`text-xs font-bold px-2 py-1 rounded-full flex items-center gap-1 ${
                          farmerPaymentSummary.pending_count === 0 && farmerPaymentSummary.paid_count > 0
                            ? 'bg-green-200 text-green-800' 
                            : farmerPaymentSummary.paid_count > 0
                            ? 'bg-yellow-200 text-yellow-800'
                            : 'bg-red-200 text-red-800'
                        }`}>
                          {farmerPaymentSummary.pending_count === 0 && farmerPaymentSummary.paid_count > 0 ? (
                            <>
                              <CheckCircle size={12} />
                              FULLY PAID
                            </>
                          ) : farmerPaymentSummary.paid_count > 0 ? (
                            <>
                              <Clock size={12} />
                              PARTIAL
                            </>
                          ) : (
                            <>
                              <AlertCircle size={12} />
                              PENDING
                            </>
                          )}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400 italic">No Data</span>
                      )}
                    </div>
                    
                    {farmerPaymentSummary ? (
                      <>
                        <div className="space-y-1">
                          <div className="flex justify-between items-baseline">
                            <p className="text-xs text-gray-600">Expected:</p>
                            <p className="text-lg font-bold text-blue-600">
                              ₹{parseFloat(farmerPaymentSummary.total_expected || 0).toLocaleString()}
                            </p>
                          </div>
                          
                          <div className="flex justify-between items-baseline">
                            <p className="text-xs text-green-600">Paid:</p>
                            <p className="text-md font-bold text-green-600">
                              ₹{parseFloat(farmerPaymentSummary.total_paid || 0).toLocaleString()}
                            </p>
                          </div>
                          
                          {farmerPaymentSummary.total_pending > 0 && (
                            <div className="flex justify-between items-baseline">
                              <p className="text-xs text-red-600">Pending:</p>
                              <p className="text-md font-bold text-red-600">
                                ₹{parseFloat(farmerPaymentSummary.total_pending).toLocaleString()}
                              </p>
                            </div>
                          )}
                        </div>

                        {/* Progress Bar */}
                        <div className="mt-3 pt-2 border-t border-gray-200">
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-gray-500">Progress</span>
                            <span className="font-bold text-gray-700">
                              {farmerPaymentSummary.completion_percentage}%
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div 
                              className={`h-2 rounded-full transition-all ${
                                farmerPaymentSummary.completion_percentage === 100 
                                  ? 'bg-green-500' 
                                  : 'bg-yellow-500'
                              }`}
                              style={{ width: `${farmerPaymentSummary.completion_percentage}%` }}
                            ></div>
                          </div>
                        </div>

                        {/* Payment Count */}
                        {farmerPayments.length > 0 && (
                          <div className="mt-2 text-xs text-gray-500">
                            {farmerPayments.length} payment{farmerPayments.length > 1 ? 's' : ''}
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-gray-400 italic">
                        No payment data
                      </p>
                    )}
                  </div>

                </div>
              </div>
            </div>

            {/* Transport Provider Details Card */}
            {data.transport_type === 'provider' && transporterName && (
              <div className="bg-white rounded-xl shadow-lg border-l-4 border-orange-500 overflow-hidden">
                <div className="p-6">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-lg font-bold text-gray-900 flex items-center">
                        <Truck className="mr-2 text-orange-500"/> 
                        {transporterName}
                      </h3>
                      <p className="text-gray-500 text-sm">Transport Provider</p>
                    </div>
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-orange-100 text-orange-800">
                      PROVIDER
                    </span>
                  </div>

                  <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-xs text-gray-500 uppercase font-bold mb-1">Transport Charges</p>
                        <p className="text-2xl font-bold text-orange-600">
                          ₹{parseFloat(data.transport_price || 0).toLocaleString()}
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
                        <p className="text-xs text-gray-500 uppercase font-bold mb-1">Transport Charges</p>
                        <p className="text-2xl font-bold text-blue-600">
                          ₹{parseFloat(data.transport_price || 0).toLocaleString()}
                        </p>
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
                        Local workforce - No transportation arranged.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            

            {/* Farmer Details */}
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
                    <p className="text-gray-900">{farmer.location}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase font-bold">Contact</p>
                    <p className="text-gray-900">{farmer.contact_no || 'N/A'}</p>
                  </div>
                  {farmer.is_dummy_id && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-bold">Farmer ID</p>
                      <p className="text-gray-900">{farmer.farmer_id}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

{/* RIGHT COLUMN: Full Job Breakdown */}
<div className="bg-gray-50 rounded-xl shadow-inner border border-gray-200 h-fit sticky top-6">
  {/* Header - Fixed */}
  <div className="bg-white px-4 py-3 border-b border-gray-200 rounded-t-xl">
    <h3 className="text-lg font-bold text-gray-900 flex items-center">
      <Layers className="mr-2 text-indigo-600" />
      Full Job Breakdown
    </h3>
  </div>
  
  {/* Scrollable Content Area */}
  <div className="overflow-y-auto max-h-[calc(100vh-200px)] p-4 scrollbar-thin scrollbar-thumb-gray-400 scrollbar-track-gray-100">
    {fullJob?.activities ? (
      <div className="space-y-4">
        {fullJob.activities.map((activity: any, idx: number) => {
          const hasAllocations = activity.allocations && activity.allocations.length > 0;
          return (
            <div key={idx} className="bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition">
              {/* Activity Header */}
              <div className="bg-gradient-to-r from-gray-100 to-gray-50 px-4 py-3 border-b border-gray-200 flex justify-between items-center">
                <span className="font-bold text-gray-800 text-sm">{activity.activity_name}</span>
                <span className="text-xs bg-white px-2.5 py-1 rounded-full font-semibold text-gray-700 shadow-sm">
                  {activity.total_area} ac
                </span>
              </div>
              
              {!hasAllocations ? (
                <div className="p-6 text-center text-gray-400 text-xs italic">
                  No allocations yet
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {activity.allocations.map((alloc: any) => {
                    const isCurrent = alloc.allocation_id === parseInt(id || '0');
                    return (
                      <div 
                        key={alloc.allocation_id} 
                        onClick={() => !isCurrent && navigate(`/allocations/${alloc.allocation_id}`)}
                        className={`p-3 transition ${
                          isCurrent 
                            ? 'bg-blue-50 border-l-4 border-blue-500 cursor-default' 
                            : 'hover:bg-gray-50 cursor-pointer hover:border-l-4 hover:border-indigo-300'
                        }`}
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <p className={`text-sm font-semibold ${isCurrent ? 'text-blue-700' : 'text-gray-800'}`}>
                              {alloc.mukkadam_name}
                            </p>
                            <div className="flex items-center gap-3 mt-1">
                              <p className="text-xs text-gray-500 flex items-center">
                                <span className="font-medium">{alloc.allocated_area} ac</span>
                              </p>
                              <p className="text-xs text-gray-500 flex items-center">
                                <Users size={10} className="mr-1" />
                                {alloc.crew_size || '?'}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-bold text-gray-700">
                              ₹{alloc.total_cost.toLocaleString()}
                            </p>
                            {isCurrent && (
                              <span className="text-[10px] uppercase font-bold text-blue-600 bg-blue-100 px-2 py-0.5 rounded-full">
                                Viewing
                              </span>
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
      <div className="text-center py-12 text-gray-500 text-sm">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto mb-3"></div>
        Loading job context...
      </div>
    )}
  </div>
</div>

        </div>
      </div>
    </div>
  );
};

export default AllocationView;
