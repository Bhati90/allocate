// components/JobsPanel.tsx
import React, { useState, useMemo } from 'react';
import { Job } from '../types/types';
import './job.css';

interface JobsPanelProps {
  jobs: Job[];
  loading: boolean;
  onRefresh: () => void;
  onFarmerSelect: (farmerId: string, farmerName: string) => void;
  clusterId: number;
}

interface FarmerSummary {
  farmerId: string;
  farmerName: string;
  plotCount: number;
  totalActivities: number;
  remainingArea: number;
  nearestDate: string | null;
  jobs: Job[];
}

const JobsPanel: React.FC<JobsPanelProps> = ({
  jobs,
  loading,
  onRefresh,
  onFarmerSelect,
  clusterId,
}) => {
  const [filter, setFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const normalizeDate = (d?: string | null) => (d ? d : null);

  const farmerSummaries = useMemo<FarmerSummary[]>(() => {
    if (!jobs || jobs.length === 0) return [];

    // Filter by priority + search on farmer
    const filtered = jobs.filter((job) => {
      const matchesFilter = filter === 'all' || job.priority === filter;
      const matchesSearch = job.farmer_name.toLowerCase().includes(searchTerm.toLowerCase());
      return matchesFilter && matchesSearch;
    });

    // Build map: farmerId => summary
    const map = new Map<string, FarmerSummary>();

    filtered.forEach((job) => {
      const farmerId = job.farmer_id;
      const farmerName = job.farmer_name;

      if (!map.has(farmerId)) {
        map.set(farmerId, {
          farmerId,
          farmerName,
          plotCount: 0,
          totalActivities: 0,
          remainingArea: 0,
          nearestDate: null,
          jobs: [],
        });
      }

      const summary = map.get(farmerId)!;
      summary.jobs.push(job);

      // Aggregate activities for this job
      (job.activities || []).forEach((a: any) => {
        summary.totalActivities += 1;
        summary.remainingArea += Number(a.remaining_area || 0);

        const d = normalizeDate(a.scheduled_date);
        if (d) {
          if (!summary.nearestDate || d < summary.nearestDate) {
            summary.nearestDate = d;
          }
        }
      });
    });

    // Calculate unique plot count per farmer
    map.forEach((summary) => {
      const uniquePlots = new Set<number>();
      summary.jobs.forEach((job) => {
        const plotId = (job as any).plot;
        if (plotId) uniquePlots.add(plotId);
      });
      summary.plotCount = uniquePlots.size;
    });

    // Sort: nearest date first, then farmer name
    const result = Array.from(map.values());
    result.sort((a, b) => {
      if (a.nearestDate && !b.nearestDate) return -1;
      if (!a.nearestDate && b.nearestDate) return 1;
      if (a.nearestDate && b.nearestDate && a.nearestDate !== b.nearestDate) {
        return a.nearestDate < b.nearestDate ? -1 : 1;
      }
      return a.farmerName.localeCompare(b.farmerName);
    });

    return result;
  }, [jobs, filter, searchTerm]);

  const activeSummaries = farmerSummaries.filter((s) => s.remainingArea > 0);
  const completedSummaries = farmerSummaries.filter((s) => s.remainingArea <= 0);

  return (
    <div className="jobs-panel">
      <div className="panel-header">
        <h2 className="panel-title">Farmers</h2>
        <button className="btn-secondary" onClick={onRefresh} disabled={loading}>
          🔄
        </button>
      </div>

      <div className="panel-content">
        {/* Search and Filter */}
        <div className="search-filter">
          <input
            type="text"
            className="form-input"
            placeholder="Search farmer..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />

          {/* <div className="filter-tabs">
            <button
              className={`filter-tab ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}
            >
              All
            </button>
            <button
              className={`filter-tab ${filter === 'HIGH' ? 'active' : ''}`}
              onClick={() => setFilter('HIGH')}
            >
              High
            </button>
            <button
              className={`filter-tab ${filter === 'MEDIUM' ? 'active' : ''}`}
              onClick={() => setFilter('MEDIUM')}
            >
              Medium
            </button>
            <button
              className={`filter-tab ${filter === 'LOW' ? 'active' : ''}`}
              onClick={() => setFilter('LOW')}
            >
              Low
            </button>
          </div> */}
        </div>

        {/* Summary list */}
        {loading ? (
          <div className="empty-state">
            <div className="loading-spinner"></div>
            <p>Loading data...</p>
          </div>
        ) : farmerSummaries.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <p className="empty-state-text">No bookings found</p>
          </div>
        ) : (
          <div className="jobs-list">
            {/* Active (remaining area > 0) */}
            {activeSummaries.map((s) => (
              <div
                key={s.farmerId}
                className="job-card"
                onClick={() => onFarmerSelect(s.farmerId, s.farmerName)}
              >
                <div className="job-header">
                  <span className="job-farmer">👤 {s.farmerName}</span>
                  <span className="job-plot-count">{s.plotCount} plot{s.plotCount !== 1 ? 's' : ''}</span>
                </div>

                <div className="job-activities">
                  <div className="activity-item">
                    <span className="activity-name">Total Activities</span>
                    <span className="activity-area">{s.totalActivities}</span>
                  </div>

                  <div className="activity-item">
                    <span className="activity-name">Remaining Area</span>
                    <span className="activity-area">{s.remainingArea.toFixed(2)} ac</span>
                  </div>
                </div>

                {s.nearestDate && (
                  <div className="job-date">
                    First activity: {new Date(s.nearestDate).toLocaleDateString()}
                  </div>
                )}
              </div>
            ))}

            {/* Completed (no remaining area) */}
            {completedSummaries.length > 0 && (
              <>
                <div className="jobs-section-divider">Completed (0 ac remaining)</div>
                {completedSummaries.map((s) => (
                  <div
                    key={s.farmerId}
                    className="job-card completed"
                    onClick={() => onFarmerSelect(s.farmerId, s.farmerName)}
                  >
                    <div className="job-header">
                      <span className="job-farmer">👤 {s.farmerName}</span>
                      <span className="job-plot-count">{s.plotCount} plot{s.plotCount !== 1 ? 's' : ''}</span>
                    </div>

                    <div className="job-activities">
                      <div className="activity-item">
                        <span className="activity-name">Total Activities</span>
                        <span className="activity-area">{s.totalActivities}</span>
                      </div>

                      <div className="activity-item">
                        <span className="activity-name">Remaining Area</span>
                        <span className="activity-area">0.00 ac</span>
                      </div>
                    </div>

                    {s.nearestDate && (
                      <div className="job-date">
                        First activity: {new Date(s.nearestDate).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default JobsPanel;
