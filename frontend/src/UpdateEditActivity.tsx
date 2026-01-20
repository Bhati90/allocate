// EditActivityModal.jsx
// Complete modal component for editing activity details

import React, { useState, useEffect } from 'react';
import { X, Save, Calendar, DollarSign, Layers } from 'lucide-react';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_ALLOCATION;
const EditActivityModal = ({ activity, jobId, isOpen, onClose, onSaveSuccess }) => {
  const [formData, setFormData] = useState({
    activity_name: '',
    acres: '',
    date_time: '',
    total_price: ''
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Initialize form with activity data when modal opens
  useEffect(() => {
    if (activity && isOpen) {
      setFormData({
        activity_name: activity.activity_name || '',
        acres: activity.total_area || activity.acres || '',
        date_time: activity.scheduled_date || activity.date_time?.split('T')[0] || '',
        total_price: activity.total_price || ''
      });
      setError('');
    }
  }, [activity, isOpen]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Prepare payload
      const payload = {
        job_id: jobId,
        activity_id: activity.activity_id || activity.id,
        updates: {
          activity_name: formData.activity_name,
          acres: parseFloat(formData.acres),
          date_time: formData.date_time ? `${formData.date_time}T12:00:00+00:00` : null,
          total_price: parseFloat(formData.total_price)
        }
      };

      console.log('📤 Sending update:', payload);

      // Call your backend endpoint
      const response = await fetch(`${API_BASE_URL}/ap/update-activity/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to update activity');
      }

      console.log('✅ Update successful:', data);

      // Call success callback to refresh jobs
      onSaveSuccess();
      
      // Close modal
      onClose();

    } catch (err) {
      console.error('❌ Update failed:', err);
      setError(err.message || 'Failed to update activity. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-800">Edit Activity</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
            disabled={loading}
          >
            <X size={24} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          {/* Activity Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Layers className="inline mr-2" size={16} />
              Activity Name
            </label>
            <input
              type="text"
              name="activity_name"
              value={formData.activity_name}
              onChange={handleInputChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
              placeholder="e.g., Finger Thinning"
              required
            />
          </div>

          {/* Acres */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Layers className="inline mr-2" size={16} />
              Area (Acres)
            </label>
            <input
              type="number"
              name="acres"
              value={formData.acres}
              onChange={handleInputChange}
              step="0.01"
              min="0"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
              placeholder="e.g., 2.5"
              required
            />
          </div>

          {/* Scheduled Date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Calendar className="inline mr-2" size={16} />
              Scheduled Date
            </label>
            <input
              type="date"
              name="date_time"
              value={formData.date_time}
              onChange={handleInputChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
              required
            />
          </div>

          {/* Total Price */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <DollarSign className="inline mr-2" size={16} />
              Total Price (₹)
            </label>
            <input
              type="number"
              name="total_price"
              value={formData.total_price}
              onChange={handleInputChange}
              step="0.01"
              min="0"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
              placeholder="e.g., 5000"
              required
            />
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition font-medium"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition font-medium flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={loading}
            >
              {loading ? (
                <>
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                  Saving...
                </>
              ) : (
                <>
                  <Save size={16} />
                  Save Changes
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default EditActivityModal;