// components/MapView/MapFilters.tsx
import React, { useState } from 'react';
import { Search, Filter, X, Calendar, MapPin, Users, TrendingUp } from 'lucide-react';
import dayjs from 'dayjs';

type FilterState = {
  search: string;
  bookingType: 'ALL' | 'TENDER' | 'ON_DEMAND';
  status: string;
  village: string;
  mukkadamName: string;
  dateFrom: string;
  dateTo: string;
  minRevenue: string;
  maxRevenue: string;
  minPenetration: string;
  maxPenetration: string;
};

type Props = {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  villages: string[];
  mukkadamNames: string[];
};

export function MapFilters({ filters, onChange, villages, mukkadamNames }: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleChange = (key: keyof FilterState, value: string) => {
    onChange({ ...filters, [key]: value });
  };

  const clearFilters = () => {
    onChange({
      search: '',
      bookingType: 'ALL',
      status: '',
      village: '',
      mukkadamName: '',
      dateFrom: '',
      dateTo: '',
      minRevenue: '',
      maxRevenue: '',
      minPenetration: '',
      maxPenetration: '',
    });
  };

  const activeFilterCount = Object.entries(filters).filter(([key, value]) => {
    if (key === 'bookingType') return value !== 'ALL';
    return value !== '';
  }).length;

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Filter className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-bold text-gray-900">Filters</h3>
          {activeFilterCount > 0 && (
            <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-bold">
              {activeFilterCount} active
            </span>
          )}
        </div>
        {activeFilterCount > 0 && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
            Clear All
          </button>
        )}
      </div>

      {/* Quick Filters */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={filters.search}
            onChange={(e) => handleChange('search', e.target.value)}
            placeholder="Search cluster, job..."
            className="w-full pl-10 pr-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Booking Type */}
        <select
          value={filters.bookingType}
          onChange={(e) => handleChange('bookingType', e.target.value as any)}
          className="px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-medium"
        >
          <option value="ALL">All Types</option>
          <option value="TENDER">Tender Only</option>
          <option value="ON_DEMAND">On-Demand Only</option>
        </select>

        {/* Status */}
        <select
          value={filters.status}
          onChange={(e) => handleChange('status', e.target.value)}
          className="px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-medium"
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="partially_allocated">Partially Allocated</option>
          <option value="fully_allocated">Fully Allocated</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
        </select>

        {/* Village */}
        <select
          value={filters.village}
          onChange={(e) => handleChange('village', e.target.value)}
          className="px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-medium"
        >
          <option value="">All Villages</option>
          {villages.sort().map((village) => (
            <option key={village} value={village}>
              {village}
            </option>
          ))}
        </select>
      </div>

      {/* Advanced Filters Toggle */}
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-800 mb-4"
      >
        <Filter className="w-4 h-4" />
        {showAdvanced ? 'Hide' : 'Show'} Advanced Filters
      </button>

      {/* Advanced Filters */}
      {showAdvanced && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
          {/* Mukkadam Name */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              <Users className="w-4 h-4 inline mr-1" />
              Mukkadam Team
            </label>
            <select
              value={filters.mukkadamName}
              onChange={(e) => handleChange('mukkadamName', e.target.value)}
              className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Teams</option>
              {mukkadamNames.sort().map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          {/* Date From */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              <Calendar className="w-4 h-4 inline mr-1" />
              Date From
            </label>
            <input
              type="date"
              value={filters.dateFrom}
              onChange={(e) => handleChange('dateFrom', e.target.value)}
              className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Date To */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              <Calendar className="w-4 h-4 inline mr-1" />
              Date To
            </label>
            <input
              type="date"
              value={filters.dateTo}
              onChange={(e) => handleChange('dateTo', e.target.value)}
              className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Min Revenue */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              <TrendingUp className="w-4 h-4 inline mr-1" />
              Min Revenue (₹)
            </label>
            <input
              type="number"
              value={filters.minRevenue}
              onChange={(e) => handleChange('minRevenue', e.target.value)}
              placeholder="0"
              className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Max Revenue */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              <TrendingUp className="w-4 h-4 inline mr-1" />
              Max Revenue (₹)
            </label>
            <input
              type="number"
              value={filters.maxRevenue}
              onChange={(e) => handleChange('maxRevenue', e.target.value)}
              placeholder="999999"
              className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Min Penetration */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              <MapPin className="w-4 h-4 inline mr-1" />
              Min Penetration (%)
            </label>
            <input
              type="number"
              value={filters.minPenetration}
              onChange={(e) => handleChange('minPenetration', e.target.value)}
              placeholder="0"
              min="0"
              max="100"
              className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Max Penetration */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              <MapPin className="w-4 h-4 inline mr-1" />
              Max Penetration (%)
            </label>
            <input
              type="number"
              value={filters.maxPenetration}
              onChange={(e) => handleChange('maxPenetration', e.target.value)}
              placeholder="100"
              min="0"
              max="100"
              className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>
      )}
    </div>
  );
}