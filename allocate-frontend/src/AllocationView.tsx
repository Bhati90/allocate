import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  ArrowLeft, Users, Truck, DollarSign, 
  Calendar, FileText, ExternalLink, Car, XCircle
} from 'lucide-react';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_SUPPLY;
const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

import { getAuthConfig } from './utils/auth';

const AllocationView: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [mukkadam, setMukkadam] = useState<any>(null);
  const [provider, setProvider] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const config = getAuthConfig();
        const allocationRes = await axios.get(`${API_BASE_URL_A}/ap/allocations/${id}/`, config);
        setData(allocationRes.data);

        // Fetch mukkadam details
        try {
          const mukkadamRes = await axios.get(
            `${API_BASE_URL}/api/mukkadam/${allocationRes.data.mukkadam_id}/`, 
            config
          );
          setMukkadam(mukkadamRes.data);
        } catch (error) {
          console.error('Failed to fetch mukkadam:', error);
          setMukkadam(null);
        }

        // Only fetch transport provider if transport_type is 'provider'
        if (allocationRes.data.transport_type === 'provider' && allocationRes.data.transport_provider_id) {
          try {
            const providerRes = await axios.get(
              `${API_BASE_URL}/api/transport-providers/${allocationRes.data.transport_provider_id}/`,
              config
            );
            setProvider(providerRes.data);
          } catch (error) {
            console.error('Failed to fetch transport provider:', error);
            setProvider(null);
          }
        }

        setLoading(false);
      } catch (error) {
        console.error('Failed to fetch allocation:', error);
        alert('Failed to load allocation details');
        navigate('/allocations');
      }
    };

    fetchData();
  }, [id, navigate]);

  if (loading || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading allocation details...</p>
        </div>
      </div>
    );
  }

  const totalCost = parseFloat(data.mukkadam_price || 0) + parseFloat(data.transport_price || 0);

  // Determine transport display info
  const getTransportDisplay = () => {
    if (data.transport_type === 'none') {
      return {
        title: 'No Transport Required',
        icon: XCircle,
        iconColor: 'text-gray-500',
        bgColor: 'bg-gray-50',
        borderColor: 'border-gray-300',
        price: 0,
        message: 'This job does not require transportation services.'
      };
    } else if (data.transport_type === 'own') {
      return {
        title: 'Own Transport',
        icon: Car,
        iconColor: 'text-blue-500',
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-300',
        price: parseFloat(data.own_transport_price || data.transport_price || 0),
        message: 'Using own transportation for this job.'
      };
    } else {
      return {
        title: 'Transport Provider',
        icon: Truck,
        iconColor: 'text-orange-500',
        bgColor: 'bg-orange-50',
        borderColor: 'border-orange-300',
        price: parseFloat(data.transport_price || 0),
        message: null
      };
    }
  };

  const transportDisplay = getTransportDisplay();
  const TransportIcon = transportDisplay.icon;

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        
        <button 
          onClick={() => navigate('/allocations')} 
          className="flex items-center text-gray-600 hover:text-black transition"
        >
          <ArrowLeft className="mr-2" size={20} /> Back to Allocations
        </button>

        {/* Header Card */}
        <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
          <div className="h-32 bg-gradient-to-r from-green-600 to-blue-600"></div>
          <div className="px-8 pb-6">
            <div className="flex items-end justify-between -mt-12">
              <div className="flex items-end">
                <div className="w-24 h-24 rounded-full border-4 border-white shadow-lg bg-green-500 flex items-center justify-center text-white text-3xl font-bold">
                  ✓
                </div>
                <div className="ml-4 mb-2">
                  <h1 className="text-2xl font-bold text-gray-900">
                    Allocation #{data.id}
                  </h1>
                  <p className="text-gray-500">
                    Allocated on {new Date(data.allocated_at).toLocaleDateString('en-IN', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </p>
                  {data.activity_name && (
                    <p className="text-sm text-purple-600 font-semibold mt-1">
                      Activity: {data.activity_name}
                    </p>
                  )}
                </div>
              </div>
              <div className="text-right mb-2">
                <p className="text-sm text-gray-500">Total Cost</p>
                <p className="text-3xl font-bold text-green-600">₹{totalCost.toLocaleString()}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Mukkadam Details */}
          <div className="bg-white p-6 rounded-xl shadow-lg border-l-4 border-blue-500">
            <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center">
              <Users className="mr-2 text-blue-500"/> Mukkadam Details
            </h3>
            
            {mukkadam ? (
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-gray-500 uppercase font-bold">Name</p>
                  <p className="text-lg font-semibold text-gray-800">{mukkadam.mukkadam_name}</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase font-bold">Mobile</p>
                    <p className="text-sm text-gray-700">{mukkadam.mobile_numbers}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase font-bold">Village</p>
                    <p className="text-sm text-gray-700">{mukkadam.village}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase font-bold">Default Crew</p>
                    <p className="text-sm font-bold text-blue-600">{mukkadam.crew_size}</p>
                  </div>
                  {data.crew_size && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-bold">This Job Crew</p>
                      <p className="text-sm font-bold text-teal-600">{data.crew_size} workers</p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-gray-500 uppercase font-bold">Mukkadam ID</p>
                    <p className="text-sm text-gray-700">#{data.mukkadam_id}</p>
                  </div>
                </div>
                <div className="pt-3 border-t">
                  <p className="text-xs text-gray-500 uppercase font-bold mb-2">Mukkadam Payment</p>
                  <p className="text-2xl font-bold text-blue-600">₹{parseFloat(data.mukkadam_price).toLocaleString()}</p>
                </div>
                <button
                  onClick={() => navigate(`/admin-view/${mukkadam.id}`)}
                  className="w-full py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 flex items-center justify-center transition"
                >
                  <ExternalLink size={16} className="mr-2" /> View Full Profile
                </button>
              </div>
            ) : (
              <div className="text-center py-8">
                <Users size={48} className="mx-auto text-gray-300 mb-2" />
                <p className="text-gray-400 italic">Mukkadam details not available</p>
              </div>
            )}
          </div>

          {/* Transport Details - Conditional Rendering */}
          <div className={`bg-white p-6 rounded-xl shadow-lg border-l-4 ${transportDisplay.borderColor}`}>
            <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center">
              <TransportIcon className={`mr-2 ${transportDisplay.iconColor}`}/> 
              {transportDisplay.title}
            </h3>
            
            {/* NO TRANSPORT */}
            {data.transport_type === 'none' && (
              <div className={`${transportDisplay.bgColor} p-6 rounded-lg border ${transportDisplay.borderColor} text-center`}>
                <XCircle size={48} className="mx-auto text-gray-400 mb-3" />
                <p className="text-gray-600 mb-4">{transportDisplay.message}</p>
                <div className="pt-4 border-t border-gray-300">
                  <p className="text-xs text-gray-500 uppercase font-bold mb-2">Transport Cost</p>
                  <p className="text-2xl font-bold text-gray-600">₹0</p>
                </div>
              </div>
            )}

            {/* OWN TRANSPORT */}
            {data.transport_type === 'own' && (
              <div className="space-y-4">
                <div className={`${transportDisplay.bgColor} p-4 rounded-lg border ${transportDisplay.borderColor}`}>
                  <div className="flex items-center justify-center mb-3">
                    <Car size={48} className={transportDisplay.iconColor} />
                  </div>
                  <p className="text-center text-gray-700 font-semibold mb-2">
                    {transportDisplay.message}
                  </p>
                </div>
                <div className="pt-3 border-t">
                  <p className="text-xs text-gray-500 uppercase font-bold mb-2">Own Transport Cost</p>
                  <p className="text-2xl font-bold text-blue-600">
                    ₹{transportDisplay.price.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-2">
                    Self-arranged transportation
                  </p>
                </div>
              </div>
            )}

            {/* TRANSPORT PROVIDER */}
            {data.transport_type === 'provider' && (
              <>
                {provider ? (
                  <div className="space-y-4">
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-bold">Name</p>
                      <p className="text-lg font-semibold text-gray-800">{provider.name}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-gray-500 uppercase font-bold">Contact</p>
                        <p className="text-sm text-gray-700">{provider.contact_number}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 uppercase font-bold">Base Location</p>
                        <p className="text-sm text-gray-700">{provider.base_location}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 uppercase font-bold">Max Distance</p>
                        <p className="text-sm text-gray-700">{provider.max_distance} km</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 uppercase font-bold">Provider ID</p>
                        <p className="text-sm text-gray-700">#{data.transport_provider_id}</p>
                      </div>
                    </div>
                    <div className="pt-3 border-t">
                      <p className="text-xs text-gray-500 uppercase font-bold mb-2">Transport Payment</p>
                      <p className="text-2xl font-bold text-orange-600">
                        ₹{parseFloat(data.transport_price).toLocaleString()}
                      </p>
                    </div>
                    <button
                      onClick={() => navigate(`/transport-providers/${provider.id}`)}
                      className="w-full py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 flex items-center justify-center transition"
                    >
                      <ExternalLink size={16} className="mr-2" /> View Full Details
                    </button>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <Truck size={48} className="mx-auto text-gray-300 mb-2" />
                    <p className="text-gray-400 italic">Provider details not available</p>
                    <div className="pt-4 mt-4 border-t">
                      <p className="text-xs text-gray-500 uppercase font-bold mb-2">Transport Payment</p>
                      <p className="text-2xl font-bold text-orange-600">
                        ₹{parseFloat(data.transport_price || 0).toLocaleString()}
                      </p>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Work Details */}
          <div className="bg-white p-6 rounded-xl shadow-lg lg:col-span-2">
            <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center">
              <FileText className="mr-2 text-green-500"/> Work & Allocation Details
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div>
                <p className="text-xs text-gray-500 uppercase font-bold">Job ID</p>
                <p className="text-lg font-mono font-semibold text-blue-600">
                  {data.job_id || data.farmer_work_id || 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase font-bold">Allocation ID</p>
                <p className="text-lg font-mono font-semibold text-gray-800">#{data.id}</p>
              </div>
              {data.work_date && (
                <div>
                  <p className="text-xs text-gray-500 uppercase font-bold">Work Date</p>
                  <p className="text-sm font-semibold text-gray-700">
                    {new Date(data.work_date).toLocaleDateString('en-IN', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </p>
                </div>
              )}
              {data.allocated_area && (
                <div>
                  <p className="text-xs text-gray-500 uppercase font-bold">Allocated Area</p>
                  <p className="text-sm font-semibold text-gray-700">{data.allocated_area} acres</p>
                </div>
              )}
              <div>
                <p className="text-xs text-gray-500 uppercase font-bold">Allocated At</p>
                <p className="text-sm text-gray-700">
                  {new Date(data.allocated_at).toLocaleString('en-IN', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </p>
              </div>
              {data.allocated_by && (
                <div>
                  <p className="text-xs text-gray-500 uppercase font-bold">Allocated By</p>
                  <p className="text-sm font-semibold text-gray-700">
                    {data.allocated_by.username || data.created_by?.username || 'System'}
                  </p>
                </div>
              )}
              <div>
                <p className="text-xs text-gray-500 uppercase font-bold">Status</p>
                <span className="inline-block px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-bold">
                  {data.status?.toUpperCase() || 'ALLOCATED'}
                </span>
              </div>
            </div>

            {/* Payment Breakdown */}
            <div className="mt-6 pt-6 border-t-2 bg-gradient-to-br from-green-50 to-blue-50 p-6 rounded-lg">
              <h4 className="font-bold text-gray-800 mb-4 text-lg">Payment Breakdown</h4>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-700 font-medium">Mukkadam Payment:</span>
                  <span className="font-bold text-blue-600 text-lg">
                    ₹{parseFloat(data.mukkadam_price).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-700 font-medium">
                    Transport Payment ({data.transport_type}):
                  </span>
                  <span className={`font-bold text-lg ${
                    data.transport_type === 'none' ? 'text-gray-500' :
                    data.transport_type === 'own' ? 'text-blue-600' :
                    'text-orange-600'
                  }`}>
                    ₹{parseFloat(data.transport_price || 0).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between items-center pt-3 border-t-2 border-green-300">
                  <span className="font-bold text-gray-800 text-lg">Total Cost:</span>
                  <span className="text-3xl font-bold text-green-600">
                    ₹{totalCost.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Notes */}
            {data.notes && (
              <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-xs text-gray-500 uppercase font-bold mb-2">Notes</p>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">{data.notes}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AllocationView;