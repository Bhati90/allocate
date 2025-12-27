import React, { useState, useEffect, FormEvent, ChangeEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Save, Users, Truck, DollarSign } from 'lucide-react';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_SUPPLY;
const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

interface Mukkadam {
  id: number;
  mukkadam_name: string;
  mobile_numbers: string;
  village: string;
  crew_size: string;
}

interface TransportProvider {
  id: number;
  name: string;
  contact_number: string;
  base_location: string;
  max_distance: number;
}

interface AllocationFormData {
  farmerWorkId: string;
  mukkadamId: string;
  transportProviderId: string;
  mukkadamPrice: string;
  transportPrice: string;
}

const AllocationForm: React.FC = () => {
  const navigate = useNavigate();

  const [mukkadams, setMukkadams] = useState<Mukkadam[]>([]);
  const [transportProviders, setTransportProviders] = useState<TransportProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [formData, setFormData] = useState<AllocationFormData>({
    farmerWorkId: '',
    mukkadamId: '',
    transportProviderId: '',
    mukkadamPrice: '',
    transportPrice: ''
  });

  // Fetch dropdown data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [mukkadamsRes, providersRes] = await Promise.all([
          axios.get(`${API_BASE_URL}/api/mukkadam/minimal_list/`),
          axios.get(`${API_BASE_URL}/api/transport-providers/dropdown_list/`)
        ]);

        setMukkadams(mukkadamsRes.data);
        setTransportProviders(providersRes.data);
      } catch (error) {
        console.error('Failed to fetch dropdown data:', error);
        alert('Failed to load data. Please refresh the page.');
      }
    };

    fetchData();
  }, []);

  const handleInputChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));

    // Clear error
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.farmerWorkId.trim()) newErrors.farmerWorkId = 'Work ID is required';
    if (!formData.mukkadamId) newErrors.mukkadamId = 'Please select a mukkadam';
    if (!formData.transportProviderId) newErrors.transportProviderId = 'Please select a transport provider';
    if (!formData.mukkadamPrice || parseFloat(formData.mukkadamPrice) <= 0) {
      newErrors.mukkadamPrice = 'Valid mukkadam price is required';
    }
    if (!formData.transportPrice || parseFloat(formData.transportPrice) <= 0) {
      newErrors.transportPrice = 'Valid transport price is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      alert('Please fix the errors before submitting');
      return;
    }

    setLoading(true);

    const payload = {
      farmer_work_id: formData.farmerWorkId,
      mukkadam_id: parseInt(formData.mukkadamId),
      transport_provider_id: parseInt(formData.transportProviderId),
      mukkadam_price: parseFloat(formData.mukkadamPrice),
      transport_price: parseFloat(formData.transportPrice)
    };

    try {
      const response = await axios.post(`${API_BASE_URL}/ap/allocations/`, payload);
      alert('Allocation created successfully!');
      console.log('Created allocation:', response.data);
      navigate('/allocations');
    } catch (error: any) {
      console.error('Submission error:', error);
      alert('Failed to create allocation: ' + (error.response?.data?.message || error.message));
    } finally {
      setLoading(false);
    }
  };

  // Get selected mukkadam and provider details
  const selectedMukkadam = mukkadams.find(m => m.id === parseInt(formData.mukkadamId));
  const selectedProvider = transportProviders.find(p => p.id === parseInt(formData.transportProviderId));

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-blue-50 to-purple-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        
        <button 
          onClick={() => navigate('/allocations')}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4 transition"
        >
          <ArrowLeft className="mr-2" /> Back to Allocations
        </button>

        <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-green-600 to-blue-600 px-6 py-8">
            <h1 className="text-3xl font-bold text-white text-center">
              Create Work Allocation
            </h1>
            <p className="text-green-50 text-center mt-2">
              Assign mukkadam and transport provider for completed work
            </p>
          </div>

          <form onSubmit={handleSubmit} className="px-6 py-8 space-y-8">
            
            {/* Work Reference */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-800 border-b-2 border-green-200 pb-2">
                Work Reference
              </h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Farmer Work ID <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="farmerWorkId"
                  value={formData.farmerWorkId}
                  onChange={handleInputChange}
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-green-500 ${
                    errors.farmerWorkId ? 'border-red-500' : 'border-gray-300'
                  }`}
                  placeholder="e.g., WORK-2024-001"
                />
                {errors.farmerWorkId && <p className="text-red-500 text-xs mt-1">{errors.farmerWorkId}</p>}
              </div>
            </section>

            {/* Mukkadam Selection */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-800 border-b-2 border-blue-200 pb-2 flex items-center">
                <Users className="mr-2" /> Mukkadam Details
              </h2>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Mukkadam <span className="text-red-500">*</span>
                </label>
                <select
                  name="mukkadamId"
                  value={formData.mukkadamId}
                  onChange={handleInputChange}
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 ${
                    errors.mukkadamId ? 'border-red-500' : 'border-gray-300'
                  }`}
                >
                  <option value="">-- Select Mukkadam --</option>
                  {mukkadams.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.mukkadam_name} ({m.mobile_numbers}) - {m.village} - Crew: {m.crew_size}
                    </option>
                  ))}
                </select>
                {errors.mukkadamId && <p className="text-red-500 text-xs mt-1">{errors.mukkadamId}</p>}
              </div>

              {selectedMukkadam && (
                <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                  <h4 className="font-semibold text-gray-700 mb-2">Selected Mukkadam Details:</h4>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-gray-600">Name:</span>
                      <span className="font-semibold ml-2">{selectedMukkadam.mukkadam_name}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Mobile:</span>
                      <span className="font-semibold ml-2">{selectedMukkadam.mobile_numbers}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Village:</span>
                      <span className="font-semibold ml-2">{selectedMukkadam.village}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Crew Size:</span>
                      <span className="font-semibold ml-2">{selectedMukkadam.crew_size}</span>
                    </div>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Mukkadam Price (₹) <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-3 text-gray-400" size={20} />
                  <input
                    type="number"
                    name="mukkadamPrice"
                    value={formData.mukkadamPrice}
                    onChange={handleInputChange}
                    className={`w-full pl-10 pr-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 ${
                      errors.mukkadamPrice ? 'border-red-500' : 'border-gray-300'
                    }`}
                    placeholder="5000.00"
                    step="0.01"
                    min="0"
                  />
                </div>
                {errors.mukkadamPrice && <p className="text-red-500 text-xs mt-1">{errors.mukkadamPrice}</p>}
              </div>
            </section>

            {/* Transport Provider Selection */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-800 border-b-2 border-orange-200 pb-2 flex items-center">
                <Truck className="mr-2" /> Transport Provider Details
              </h2>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Transport Provider <span className="text-red-500">*</span>
                </label>
                <select
                  name="transportProviderId"
                  value={formData.transportProviderId}
                  onChange={handleInputChange}
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-orange-500 ${
                    errors.transportProviderId ? 'border-red-500' : 'border-gray-300'
                  }`}
                >
                  <option value="">-- Select Transport Provider --</option>
                  {transportProviders.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.contact_number}) - {p.base_location} - Max: {p.max_distance}km
                    </option>
                  ))}
                </select>
                {errors.transportProviderId && <p className="text-red-500 text-xs mt-1">{errors.transportProviderId}</p>}
              </div>

              {selectedProvider && (
                <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                  <h4 className="font-semibold text-gray-700 mb-2">Selected Provider Details:</h4>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-gray-600">Name:</span>
                      <span className="font-semibold ml-2">{selectedProvider.name}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Contact:</span>
                      <span className="font-semibold ml-2">{selectedProvider.contact_number}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Base Location:</span>
                      <span className="font-semibold ml-2">{selectedProvider.base_location}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Max Distance:</span>
                      <span className="font-semibold ml-2">{selectedProvider.max_distance} km</span>
                    </div>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Transport Price (₹) <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-3 text-gray-400" size={20} />
                  <input
                    type="number"
                    name="transportPrice"
                    value={formData.transportPrice}
                    onChange={handleInputChange}
                    className={`w-full pl-10 pr-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-orange-500 ${
                      errors.transportPrice ? 'border-red-500' : 'border-gray-300'
                    }`}
                    placeholder="1500.00"
                    step="0.01"
                    min="0"
                  />
                </div>
                {errors.transportPrice && <p className="text-red-500 text-xs mt-1">{errors.transportPrice}</p>}
              </div>
            </section>

            {/* Summary */}
            {formData.mukkadamPrice && formData.transportPrice && (
              <div className="bg-green-50 p-6 rounded-lg border-2 border-green-200">
                <h3 className="font-bold text-gray-800 mb-3">Allocation Summary</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">Mukkadam Price</p>
                    <p className="text-2xl font-bold text-blue-600">₹ {parseFloat(formData.mukkadamPrice).toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Transport Price</p>
                    <p className="text-2xl font-bold text-orange-600">₹ {parseFloat(formData.transportPrice).toFixed(2)}</p>
                  </div>
                  <div className="col-span-2 pt-3 border-t-2 border-green-300">
                    <p className="text-sm text-gray-600">Total Cost</p>
                    <p className="text-3xl font-bold text-green-600">
                      ₹ {(parseFloat(formData.mukkadamPrice) + parseFloat(formData.transportPrice)).toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Submit Button */}
            <div className="pt-6">
              <button
                type="submit"
                disabled={loading}
                className={`w-full flex items-center justify-center text-white font-semibold py-4 px-6 rounded-lg transition shadow-lg ${
                  loading 
                    ? 'bg-gray-400 cursor-not-allowed' 
                    : 'bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700'
                }`}
              >
                {loading ? (
                  'Creating Allocation...'
                ) : (
                  <>
                    <Save className="mr-2" size={20} />
                    Create Allocation
                  </>
                )}
              </button>
            </div>

          </form>
        </div>
      </div>
    </div>
  );
};

export default AllocationForm;