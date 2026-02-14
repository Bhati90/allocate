// LinkFarmerPaymentModal.tsx

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, Search, AlertCircle, CheckCircle, TrendingUp, Calendar, DollarSign } from 'lucide-react';
import { getAuthConfig } from './utils/auth';

const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

interface UnmatchedPayment {
  id: number;
  farmer_name: string;
  activity_name: string;
  activity_date: string;
  booking_value: number;
  payment_status: string;
  payment_route: string;
  date_of_payment: string | null;
  village: string;
  acres: string;
  reference_no: string;
  description: string;
  match_suggestion?: {
    job_activity_id: number;
    job_id: string;
    activity_name: string;
    scheduled_date: string;
  };
  confidence?: 'high' | 'medium' | 'low';
  score?: number;
  reasons?: string[];
}

interface LinkFarmerPaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobActivityId: number;
  jobId: string;
  activityName: string;
  onPaymentLinked: () => void;
}

const LinkFarmerPaymentModal: React.FC<LinkFarmerPaymentModalProps> = ({
  isOpen,
  onClose,
  jobActivityId,
  jobId,
  activityName,
  onPaymentLinked
}) => {
  const [payments, setPayments] = useState<UnmatchedPayment[]>([]);
  const [loading, setLoading] = useState(false);
  const [linking, setLinking] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  
const fetchUnmatchedPayments = async () => {
  // ✅ VALIDATION
  if (!jobActivityId || jobActivityId === 0) {
    console.error('❌ Invalid jobActivityId:', jobActivityId);
    setPayments([]);
    setLoading(false);
    return;
  }
  
  console.log('🔍 Fetching unmatched payments for activity:', jobActivityId);
  
  setLoading(true);
  try {
    const config = getAuthConfig();
    const params = new URLSearchParams({
      job_activity_id: String(jobActivityId), // ✅ Use String() instead of .toString()
    });
    
    if (searchQuery) params.append('farmer_name', searchQuery);
    if (filterStatus !== 'all') params.append('payment_status', filterStatus);
    
    console.log('📡 Request URL:', `${API_BASE_URL_A}/ap/unmatched-farmer-payments/?${params.toString()}`);
    
    const response = await axios.get(
      `${API_BASE_URL_A}/ap/unmatched-farmer-payments/?${params.toString()}`,
      config
    );
    
    console.log('✅ Received payments:', response.data.payments?.length || 0);
    setPayments(response.data.payments || []);
  } catch (error: any) {
    console.error('❌ Error fetching unmatched payments:', error);
    console.error('Error details:', error.response?.data);
    setPayments([]);
  } finally {
    setLoading(false);
  }
};

useEffect(() => {
  if (isOpen && jobActivityId) { // ✅ ADD jobActivityId check
    fetchUnmatchedPayments();
  }
}, [isOpen, jobActivityId]);
  useEffect(() => {
    if (isOpen) {
      fetchUnmatchedPayments();
    }
  }, [isOpen, jobActivityId]);
  
  // Link payment
  const handleLinkPayment = async (paymentId: number) => {
    setLinking(true);
    try {
      const config = getAuthConfig();
      await axios.post(
        `${API_BASE_URL_A}/ap/link-farmer-payment/`,
        {
          farmer_payment_id: paymentId,
          job_activity_id: jobActivityId,
          notes: `Linked via UI for ${activityName}`
        },
        config
      );
      
      // Success - remove from list and notify parent
      setPayments(prev => prev.filter(p => p.id !== paymentId));
      onPaymentLinked();
      
      // Close if no more payments
      if (payments.length === 1) {
        onClose();
      }
    } catch (error: any) {
      console.error('Error linking payment:', error);
      alert(error.response?.data?.error || 'Failed to link payment');
    } finally {
      setLinking(false);
    }
  };
  
  // Apply search filter
  const filteredPayments = payments.filter(payment => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      if (!payment.farmer_name.toLowerCase().includes(query) &&
          !payment.village.toLowerCase().includes(query)) {
        return false;
      }
    }
    return true;
  });
  
  // Confidence badge
  const ConfidenceBadge = ({ confidence }: { confidence?: string }) => {
    if (!confidence) return null;
    
    const colors = {
      high: 'bg-green-100 text-green-700 border-green-300',
      medium: 'bg-yellow-100 text-yellow-700 border-yellow-300',
      low: 'bg-gray-100 text-gray-700 border-gray-300'
    };
    
    return (
      <span className={`px-2 py-1 rounded text-xs font-semibold border ${colors[confidence as keyof typeof colors]}`}>
        {confidence.toUpperCase()} MATCH
      </span>
    );
  };
  
  if (!isOpen) return null;
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-5xl w-full max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 p-6 text-white">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-2xl font-bold">Link Farmer Payment</h2>
              <p className="text-sm mt-1 opacity-90">
                {activityName} • Job #{jobId}
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:bg-white hover:bg-opacity-20 rounded-full p-2"
            >
              <X size={24} />
            </button>
          </div>
        </div>
        
        {/* Search & Filters */}
        <div className="p-4 bg-gray-50 border-b">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="text"
                placeholder="Search by farmer name or village..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Status</option>
              <option value="paid">Paid Only</option>
              <option value="pending">Pending Only</option>
            </select>
            
            <button
              onClick={fetchUnmatchedPayments}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              {loading ? 'Loading...' : 'Search'}
            </button>
          </div>
        </div>
        
        {/* Payments List */}
        <div className="p-6 overflow-y-auto max-h-[calc(85vh-200px)]">
          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading unmatched payments...</p>
            </div>
          ) : filteredPayments.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-xl border-2 border-dashed">
              <AlertCircle size={48} className="mx-auto text-gray-400 mb-4" />
              <p className="text-gray-600 text-lg font-medium">No unmatched payments found</p>
              <p className="text-gray-500 text-sm mt-2">
                All available payments might already be linked, or try adjusting your search
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredPayments.map((payment) => (
                <div
                  key={payment.id}
                  className={`border-2 rounded-xl p-5 transition hover:shadow-lg ${
                    payment.confidence === 'high' 
                      ? 'border-green-200 bg-green-50' 
                      : payment.confidence === 'medium'
                      ? 'border-yellow-200 bg-yellow-50'
                      : 'border-gray-200 bg-white'
                  }`}
                >
                  {/* Header Row */}
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h4 className="font-bold text-lg text-gray-900">{payment.farmer_name}</h4>
                        <ConfidenceBadge confidence={payment.confidence} />
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          payment.payment_status === 'paid' 
                            ? 'bg-green-100 text-green-700' 
                            : 'bg-orange-100 text-orange-700'
                        }`}>
                          {payment.payment_status.toUpperCase()}
                        </span>
                      </div>
                      
                      <p className="text-sm text-gray-600">
                        {payment.activity_name} • {payment.village} • {payment.acres} acres
                      </p>
                    </div>
                    
                    <div className="text-right ml-4">
                      <p className="text-sm text-gray-600 mb-1">Payment Amount</p>
                      <p className="text-2xl font-bold text-green-600">
                        ₹{payment.booking_value.toLocaleString()}
                      </p>
                    </div>
                  </div>
                  
                  {/* Details Row */}
                  <div className="grid grid-cols-3 gap-4 mb-3 text-sm">
                    <div className="flex items-center gap-2">
                      <Calendar size={16} className="text-gray-400" />
                      <div>
                        <p className="text-gray-600">Activity Date</p>
                        <p className="font-semibold">{new Date(payment.activity_date).toLocaleDateString('en-IN')}</p>
                      </div>
                    </div>
                    
                    {payment.date_of_payment && (
                      <div className="flex items-center gap-2">
                        <CheckCircle size={16} className="text-green-600" />
                        <div>
                          <p className="text-gray-600">Paid On</p>
                          <p className="font-semibold">{new Date(payment.date_of_payment).toLocaleDateString('en-IN')}</p>
                        </div>
                      </div>
                    )}
                    
                    <div className="flex items-center gap-2">
                      <DollarSign size={16} className="text-gray-400" />
                      <div>
                        <p className="text-gray-600">Payment Route</p>
                        <p className="font-semibold">{payment.payment_route || 'N/A'}</p>
                      </div>
                    </div>
                  </div>
                  
                  {/* Match Reasons */}
                  {payment.reasons && payment.reasons.length > 0 && (
                    <div className="bg-white rounded-lg p-3 mb-3 border border-gray-200">
                      <p className="text-xs font-semibold text-gray-700 mb-2">Why this matches:</p>
                      <div className="flex flex-wrap gap-2">
                        {payment.reasons.map((reason, idx) => (
                          <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
                            ✓ {reason}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Description */}
                  {payment.description && (
                    <p className="text-sm text-gray-600 mb-3 italic">
                      Note: {payment.description}
                    </p>
                  )}
                  
                  {/* Action Button */}
                  <button
                    onClick={() => handleLinkPayment(payment.id)}
                    disabled={linking}
                    className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-semibold flex items-center justify-center gap-2"
                  >
                    <CheckCircle size={18} />
                    {linking ? 'Linking...' : 'Link This Payment'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LinkFarmerPaymentModal;