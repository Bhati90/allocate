// components/JobDetailPanel.tsx
import React, { useState, useEffect } from 'react';
import { Plus, Trash2,Edit, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { Job } from '../types/types';
import './job.css';
import { API_BASE_URL } from '@/types/config';

interface Props {
  selectedFarmerId: string | null;
  selectedFarmerName: string | null;
  onActivityAdded: () => void;
  clusterId: number;
}

type PlotSummary = {
  bookedArea: number;
  allocatedArea: number;
  remainingArea: number;
};

type ActivityStatus = 'GREEN' | 'YELLOW' | 'RED';

interface ActivityRevenueRow {
  activityId: number;
  activityName: string;
  status: ActivityStatus;
  bookedArea: number;
  unbookedArea: number;
  bookedRate: number;
  clusterDefaultRate: number;
  bookedRevenue: number;
  potentialRevenue: number;
  potentialDate: string | null;
}

// NEW: Types for booked vs not-booked activities
interface BookedActivity {
  activity_id: number;
  activity_name: string;
  total_area: number;
  rate_per_acre: number;
  scheduled_date: string;
  is_strict: boolean;
}

interface NotBookedActivity {
  activity_id: number;
  activity_name: string;
  default_rate_per_acre: number;
  is_strict: boolean;
  estimated_workers_per_acre: number;
  selected: boolean;
  total_area: number;
  rate_per_acre: number;
  scheduled_date: string;
}

const buildActivityRevenueRows = (
  plot: any,
  jobsOnPlot: Job[],
  calendar: any[],
  selectedPlotId: number
): ActivityRevenueRow[] => {
  if (!plot) return [];
  const plotArea = Number(plot.area_acres || 0);
  if (!plotArea) return [];

  const rows: ActivityRevenueRow[] = [];

  const allBookedDatesOnThisPlot: string[] = [];
  jobsOnPlot.forEach((job: any) => {
    (job.activities || []).forEach((a: any) => {
      if (Number(a.plot) === selectedPlotId && a.scheduled_date) {
        allBookedDatesOnThisPlot.push(a.scheduled_date);
      }
    });
  });
  allBookedDatesOnThisPlot.sort();
  const baseDate =
    allBookedDatesOnThisPlot.length > 0 ? new Date(allBookedDatesOnThisPlot[0]) : new Date();

  calendar.forEach((cal: any, index: number) => {
    const actId = Number(cal.activity_id);
    const activityName = cal.activity_name;
    const clusterRate = Number(cal.rate_per_acre || 0);

    const jobActs: any[] = [];
    jobsOnPlot.forEach((job: any) => {
      (job.activities || []).forEach((a: any) => {
        if (Number(a.activity_id) === actId && Number(a.plot) === selectedPlotId) {
          jobActs.push(a);
        }
      });
    });

    const bookedArea = jobActs.reduce((sum, a) => sum + Number(a.total_area || 0), 0);
    const unbookedArea = Math.max(plotArea - bookedArea, 0);

    const bookedRate = jobActs.length ? Number(jobActs[0].rate_per_acre || 0) : clusterRate;

const offsetDays = index === 0 ? 0 : Number(cal.gap_days || 0);  // flat from pruning
    const d = new Date(baseDate);
    d.setDate(d.getDate() + offsetDays);
    const potentialDateIso = d.toISOString().split('T')[0];

    let status: ActivityStatus;
    let bookedRevenue = 0;
    let potentialRevenue = 0;

    if (bookedArea === 0) {
      status = 'RED';
      bookedRevenue = 0;
      potentialRevenue = plotArea * clusterRate;
    } else if (bookedArea >= plotArea) {
      status = 'GREEN';
      bookedRevenue = plotArea * bookedRate;
      potentialRevenue = 0;
    } else {
      status = 'YELLOW';
      bookedRevenue = bookedArea * bookedRate;
      potentialRevenue = unbookedArea * bookedRate;
    }

    rows.push({
      activityId: actId,
      activityName,
      status,
      bookedArea,
      unbookedArea,
      bookedRate,
      clusterDefaultRate: clusterRate,
      bookedRevenue,
      potentialRevenue,
      potentialDate: potentialDateIso,
    });
  });

  return rows;
};

const JobDetailPanel: React.FC<Props> = ({
  selectedFarmerId,
  selectedFarmerName,
  onActivityAdded,
  clusterId,
}) => {
  const [farmerPlots, setFarmerPlots] = useState<any[]>([]);
  const [selectedPlotId, setSelectedPlotId] = useState<number | null>(null);
  const [selectedPlot, setSelectedPlot] = useState<any>(null);
  const [plotJobs, setPlotJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const [farmers, setFarmers] = useState<any[]>([]);
  const [clusterCalendar, setClusterCalendar] = useState<any[]>([]);
  const [clusterInfo, setClusterInfo] = useState<any>(null);
  const [allActivities, setAllActivities] = useState<any[]>([]);

  const [showAddJobModal, setShowAddJobModal] = useState(false);
  const [showAddActivityModal, setShowAddActivityModal] = useState(false);

  const [isNewFarmer, setIsNewFarmer] = useState<boolean>(!selectedFarmerId);

  // New Job Form
  const [newJob, setNewJob] = useState({
    farmer_id: '',
    farmer_name: '',
    mobile_number: '',
    crop_name: '',
    variety: '',
    booking_amount: 0,
    payment_status: 'pending',
    base_date: '',
  });

  // New Plot Form
  const [newPlot, setNewPlot] = useState({
    name: '',
    area_acres: 0,
    plot_code: '',
  });

  // NEW: Booked and Not-Booked Activities
  const [bookedActivities, setBookedActivities] = useState<BookedActivity[]>([]);
  const [notBookedActivities, setNotBookedActivities] = useState<NotBookedActivity[]>([]);

  const [autoFilledActivities, setAutoFilledActivities] = useState<any[]>([]);

  const [newActivity, setNewActivity] = useState({
    activity_id: 0,
    total_area: 0,
    rate_per_acre: 0,
    is_strict: false,
    scheduled_date: '',
  });

  const [plotMode, setPlotMode] = useState<'existing' | 'new'>('existing');

  useEffect(() => {
    loadFarmers();
    loadClusterCalendar();
    loadClusterInfo();
    loadAllActivities();
  }, [clusterId]);

  useEffect(() => {
    setIsNewFarmer(!selectedFarmerId);
    setFarmerPlots([]);
    setSelectedPlotId(null);
    setSelectedPlot(null);
    setSelectedJob(null);

    if (selectedFarmerId) {
      loadFarmerPlots(selectedFarmerId);
    }
  }, [selectedFarmerId]);

  useEffect(() => {
    if (selectedPlotId) {
      loadPlotJobs(selectedPlotId);
    }
  }, [selectedPlotId]);

  useEffect(() => {
    if (isNewFarmer) {
      setPlotMode('new');
      setSelectedPlotId(null);
      setSelectedPlot(null);
    }
  }, [isNewFarmer]);

  const loadFarmers = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/farmers/?cluster_id=${clusterId}`
      );
      const data = await response.json();
      setFarmers(data);
    } catch (error) {
      console.error('Failed to load farmers');
    }
  };

  const loadFarmerPlots = async (farmerId: string) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/plots/?farmer_id=${farmerId}`
      );
      const data = await response.json();
      setFarmerPlots(data);
    } catch (error) {
      console.error('Failed to load farmer plots');
      setFarmerPlots([]);
    }
  };
// Add to state in JobDetailPanel
const [showEditActivityModal, setShowEditActivityModal] = useState(false);
const [editingActivity, setEditingActivity] = useState<any>(null);

// Add edit handler
const handleEditActivity = async () => {
  if (!editingActivity) return;

  // Validate total_area >= allocated_area on frontend too
  if (editingActivity.total_area < editingActivity.allocated_area) {
    toast.error(
      `Total area (${editingActivity.total_area} ac) cannot be less than allocated area (${editingActivity.allocated_area} ac)`
    );
    return;
  }

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/job-activities/${editingActivity.id}/`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          total_area: editingActivity.total_area,
          rate_per_acre: editingActivity.rate_per_acre,
          scheduled_date: editingActivity.scheduled_date,
          is_strict: editingActivity.is_strict,
        }),
      }
    );

    if (response.ok) {
      toast.success('Activity updated!');
      setShowEditActivityModal(false);
      setEditingActivity(null);
      if (selectedPlotId) {
        loadPlotJobs(selectedPlotId);
      }
      onActivityAdded();
    } else {
      const error = await response.json();
      toast.error(error.error || 'Failed to update activity');
    }
  } catch (error) {
    toast.error('Failed to update activity');
    console.error(error);
  }
};
  const loadPlotJobs = async (plotId: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs/?plot=${plotId}`);
      const data = await response.json();
      setPlotJobs(data);

      if (data.length > 0) {
        setSelectedJob(data[0]);
      } else {
        setSelectedJob(null);
      }
    } catch (error) {
      console.error('Failed to load plot jobs');
      setPlotJobs([]);
      setSelectedJob(null);
    }
  };

  const loadClusterCalendar = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/clusters/${clusterId}/activity-calendar/`
      );
      const data = await response.json();
      setClusterCalendar(data.activities || []);
    } catch (error) {
      console.error('Failed to load cluster calendar');
    }
  };

  const loadClusterInfo = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/clusters/${clusterId}/info/`);
      const data = await response.json();
      setClusterInfo(data);
    } catch (error) {
      console.error('Failed to load cluster info');
    }
  };

  const loadAllActivities = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/activities/`);
      const data = await response.json();
      setAllActivities(data);
    } catch (error) {
      console.error('Failed to load activities');
    }
  };

  // NEW: Load booked and not-booked activities for selected plot
  const loadPlotActivityStatus = async (plotId: number, plotArea: number) => {
    try {
      // Get all jobs for this plot
      const jobsResponse = await fetch(
        `${API_BASE_URL}/api/jobs/?cluster_id=${clusterId}&plot=${plotId}`
      );
      const jobs = await jobsResponse.json();

      // Extract booked activities
      const booked: BookedActivity[] = [];
      const bookedActivityIds = new Set<number>();

      jobs.forEach((job: any) => {
        (job.activities || []).forEach((activity: any) => {
          booked.push({
            activity_id: activity.activity_id,
            activity_name: activity.activity_name,
            total_area: Number(activity.total_area),
            rate_per_acre: Number(activity.rate_per_acre),
            scheduled_date: activity.scheduled_date,
            is_strict: activity.is_strict,
          });
          bookedActivityIds.add(activity.activity_id);
        });
      });

      // Get not-booked activities from all activities
      const notBooked: NotBookedActivity[] = allActivities
        .filter((act) => !bookedActivityIds.has(act.id))
        .map((act) => ({
          activity_id: act.id,
          activity_name: act.name,
          default_rate_per_acre: Number(act.default_rate_per_acre || 0),
          is_strict: act.is_strict,
          estimated_workers_per_acre: act.estimated_workers_per_acre,
          selected: false,
          total_area: plotArea,
          rate_per_acre: Number(act.default_rate_per_acre || 0),
          scheduled_date: '',
        }));

      setBookedActivities(booked);
      setNotBookedActivities(notBooked);

      // Auto-fill crop and variety from latest job
      if (jobs.length > 0) {
        const latestJob = jobs[0];
        setNewJob((prev) => ({
          ...prev,
          crop_name: latestJob.crop_name || '',
          variety: latestJob.variety || '',
        }));
      }
    } catch (error) {
      console.error('Failed to load plot activity status');
    }
  };

const autoFillActivitiesFromCalendar = (plotArea: number, baseDate: string) => {
    const base = new Date(baseDate);

    const filled = clusterCalendar.map((cal, index) => {
      // index 0 = pruning = day 0 (base date itself)
      // all others = base + their own gap_days directly
      const offsetDays = index === 0 ? 0 : cal.gap_days;

      const activityDate = new Date(base);
      activityDate.setDate(activityDate.getDate() + offsetDays);

      return {
        activity_id: cal.activity_id,
        activity_name: cal.activity_name,
        total_area: plotArea,
        rate_per_acre: cal.rate_per_acre,
        is_strict: cal.is_strict,
        scheduled_date: activityDate.toISOString().split('T')[0],
        enabled: true,
      };
    });

    setAutoFilledActivities(filled);
    recalcBookingAmount(filled.filter((a) => a.enabled));
  };

  const handleNewPlotAreaChange = (area: number) => {
    setNewPlot({ ...newPlot, area_acres: area });
    if (newJob.base_date && area > 0) {
      autoFillActivitiesFromCalendar(area, newJob.base_date);
    }
  };

  const handleBaseDateChange = (date: string) => {
    setNewJob({ ...newJob, base_date: date });

    if (newPlot.area_acres > 0) {
      autoFillActivitiesFromCalendar(newPlot.area_acres, date);
    }
  };

  const recalcBookingAmount = (activitiesList: any[]) => {
    const total = activitiesList.reduce(
      (sum, a) => sum + (a.total_area || 0) * (a.rate_per_acre || 0),
      0
    );
    setNewJob((prev) => ({ ...prev, booking_amount: total }));
  };

  // NEW: Calculate booking amount from selected not-booked activities
  const recalcBookingAmountFromNotBooked = () => {
    const total = notBookedActivities
      .filter((a) => a.selected)
      .reduce((sum, a) => sum + a.total_area * a.rate_per_acre, 0);
    setNewJob((prev) => ({ ...prev, booking_amount: total }));
  };

  const handleCreateJob = async () => {
    try {
      let farmerId = selectedFarmerId || newJob.farmer_id;

      // Step 1: Create farmer if new
      if (isNewFarmer || !farmerId) {
        if (!newJob.farmer_name.trim()) {
          toast.error('Enter farmer name');
          return;
        }

        const farmerResponse = await fetch(`${API_BASE_URL}/api/farmers/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            farmer_id: `F${Date.now()}`,
            farmer_name: newJob.farmer_name,
            phone_number: newJob.mobile_number,
            cluster: clusterId,
          }),
        });

        if (!farmerResponse.ok) {
          throw new Error('Failed to create farmer');
        }

        const farmer = await farmerResponse.json();
        farmerId = farmer.farmer_id;
      }

      // Step 2: Decide plot
      let plotId: number | null = null;

      if (plotMode === 'existing' && !isNewFarmer) {
        if (!selectedPlotId) {
          toast.error('Please select a plot for this job');
          return;
        }
        plotId = selectedPlotId;
      } else {
        // Create NEW plot
        if (newPlot.area_acres <= 0) {
          toast.error('Please enter plot size');
          return;
        }

        const plotResponse = await fetch(`${API_BASE_URL}/api/plots/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            farmer: farmerId,
            cluster: clusterId,
            name: newPlot.name || `Plot ${Date.now()}`,
            area_acres: newPlot.area_acres,
            plot_code: newPlot.plot_code || `P${Date.now()}`,
          }),
        });

        if (!plotResponse.ok) {
          throw new Error('Failed to create plot');
          }

        const plot = await plotResponse.json();
        plotId = plot.id;
      }

      if (!plotId) {
        toast.error('Could not determine plot');
        return;
      }

      // Step 3: Determine which activities to create
      let activitiesToCreate: any[] = [];

      if (plotMode === 'existing' && !isNewFarmer) {
        // Use selected not-booked activities
        const selectedActivities = notBookedActivities.filter((a) => a.selected);
        
        if (selectedActivities.length === 0) {
          toast.error('Please select at least one activity');
          return;
        }

        activitiesToCreate = selectedActivities.map((a) => ({
          activity_id: a.activity_id,
          activity_name: a.activity_name,
          total_area: a.total_area,
          rate_per_acre: a.rate_per_acre,
          is_strict: a.is_strict,
          scheduled_date: a.scheduled_date || null,
        }));
      } else {
        // Use auto-filled activities (for new farmer or new plot)
        activitiesToCreate = autoFilledActivities
          .filter((a) => a.enabled)
          .map((a) => ({
            activity_id: a.activity_id,
            activity_name: a.activity_name,
            total_area: a.total_area,
            rate_per_acre: a.rate_per_acre,
            is_strict: a.is_strict,
            scheduled_date: a.scheduled_date || null,
          }));
      }

      // Step 4: Create job
      const jobResponse = await fetch(`${API_BASE_URL}/api/jobs/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: `JOB${Date.now()}`,
          work_id: `WORK${Date.now()}`,
          farmer: farmerId,
          plot: plotId,
          crop_name: newJob.crop_name,
          variety: newJob.variety,
          status: 'pending',
          priority: 'MEDIUM',
          booking_type: 'Direct',
          scheduled_date: activitiesToCreate[0]?.scheduled_date || null,
          activity_notes: '',
          internal_notes: '',
          cluster: clusterId,
          booking_amount: newJob.booking_amount,
          payment_status: newJob.payment_status,
        }),
      });

      if (!jobResponse.ok) {
        throw new Error('Failed to create job');
      }

      const jobData = await jobResponse.json();

      // Step 5: Create activities
      for (const a of activitiesToCreate) {
        if (!a.activity_id || a.total_area <= 0) continue;

        await fetch(`${API_BASE_URL}/api/jobs/${jobData.job_id}/add_activity/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            activity_id: a.activity_id,
            plot: plotId,
            total_area: a.total_area,
            rate_per_acre: a.rate_per_acre,
            is_strict: a.is_strict,
            scheduled_date: a.scheduled_date,
          }),
        });
      }

      toast.success('Job created successfully!');
      setShowAddJobModal(false);
      resetJobForm();

      if (farmerId) {
        loadFarmerPlots(farmerId);
      }

      onActivityAdded();
    } catch (error) {
      toast.error('Failed to create job');
      console.error(error);
    }
  };

  const handleAddActivity = async () => {
    if (!selectedJob || newActivity.activity_id === 0) {
      toast.error('Please select an activity');
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/jobs/${selectedJob.job_id}/add_activity/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            activity_id: newActivity.activity_id,
            plot: selectedPlotId,
            total_area: newActivity.total_area,
            rate_per_acre: newActivity.rate_per_acre,
            is_strict: newActivity.is_strict,
            scheduled_date: newActivity.scheduled_date || null,
          }),
        }
      );

      if (response.ok) {
        toast.success('Activity added!');
        setShowAddActivityModal(false);
        resetActivityForm();
        if (selectedPlotId) {
          loadPlotJobs(selectedPlotId);
        }
        onActivityAdded();
      } else {
        toast.error('Failed to add activity');
      }
    } catch (error) {
      toast.error('Failed to add activity');
      console.error(error);
    }
  };

  const handleDeleteActivity = async (activityId: number) => {
    if (!confirm('Delete this activity?')) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/job-activities/${activityId}/`,
        { method: 'DELETE' }
      );

      if (response.ok) {
        toast.success('Activity deleted!');
        if (selectedPlotId) {
          loadPlotJobs(selectedPlotId);
        }
        onActivityAdded();
      } else {
        toast.error('Failed to delete');
      }
    } catch (error) {
      toast.error('Failed to delete');
      console.error(error);
    }
  };

  const loadJobsForPlot = async (plotId: number) => {
    const res = await fetch(
      `${API_BASE_URL}/api/jobs/?cluster_id=${clusterId}&plot=${plotId}`
    );
    const data = await res.json();
    setPlotJobs(data);
    if (data.length > 0) {
      setSelectedJob(data[0]);
    }
  };

  const resetJobForm = () => {
    setNewJob({
      farmer_id: '',
      farmer_name: '',
      mobile_number: '',
      crop_name: '',
      variety: '',
      booking_amount: 0,
      payment_status: 'pending',
      base_date: '',
    });
    setNewPlot({
      name: '',
      area_acres: 0,
      plot_code: '',
    });
    setIsNewFarmer(!selectedFarmerId);
    setAutoFilledActivities([]);
    setBookedActivities([]);
    setNotBookedActivities([]);
  };

  const resetActivityForm = () => {
    setNewActivity({
      activity_id: 0,
      total_area: 0,
      rate_per_acre: 0,
      is_strict: false,
      scheduled_date: '',
    });
  };

  const [farmerJobs, setFarmerJobs] = useState<any[]>([]);

  useEffect(() => {
    if (!selectedFarmerId) {
      setFarmerJobs([]);
      return;
    }
    const loadFarmerJobs = async () => {
      const res = await fetch(
        `${API_BASE_URL}/api/jobs/?cluster_id=${clusterId}&farmer_id=${selectedFarmerId}`
      );
      const data = await res.json();
      setFarmerJobs(data);
    };
    loadFarmerJobs();
  }, [selectedFarmerId, clusterId]);

  const plotSummaries: Record<number, PlotSummary> = {};

  farmerJobs.forEach((job: any) => {
    (job.activities || []).forEach((act: any) => {
      const plotId = Number(act.plot || job.plot);
      if (!plotId) return;

      if (!plotSummaries[plotId]) {
        plotSummaries[plotId] = { bookedArea: 0, allocatedArea: 0, remainingArea: 0 };
      }

      plotSummaries[plotId].bookedArea += Number(act.total_area || 0);
      plotSummaries[plotId].allocatedArea += Number(act.allocated_area || 0);
      plotSummaries[plotId].remainingArea += Number(act.remaining_area || 0);
    });
  });

  const activityRevenueRows =
    selectedPlot && selectedPlotId != null
      ? buildActivityRevenueRows(selectedPlot, plotJobs, clusterCalendar, selectedPlotId)
      : [];

  return (
    <div className="panel">
      {/* Header */}
      <div className="panel-header">
        <h2 className="panel-title">
          {selectedFarmerName ? `${selectedFarmerName}'s Jobs` : 'Job Details'}
        </h2>
        <div className="flex gap-2">
          <button
            className="btn-secondary"
            onClick={() => setShowAddJobModal(true)}
            title="Create Job"
          >
            Add new Farmer
            <Plus size={16} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="panel-content">
        {!selectedFarmerId ? (
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <p className="empty-state-text">
              Select a farmer on the left, or click "+" to create job for a new farmer.
            </p>
          </div>
        ) : !selectedPlotId ? (
          <div className="plot-selector">
            <h3 className="selector-title">Select a Plot</h3>
            <p className="selector-subtitle">Choose a plot to view its jobs and activities</p>

            {farmerPlots.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📍</div>
                <p className="empty-state-text">No plots for this farmer yet</p>
                <button onClick={() => setShowAddJobModal(true)} className="btn-primary mt-4">
                  + Create First Job
                </button>
              </div>
            ) : (
              <div className="plot-list">
                {farmerPlots.map((plot) => {
                  const summary = plotSummaries[plot.id] || {
                    bookedArea: 0,
                    allocatedArea: 0,
                    remainingArea: 0,
                  };

                  return (
                    <button
                      key={plot.id}
                      className="plot-card"
                      onClick={() => {
                        setSelectedPlotId(plot.id);
                        setSelectedPlot(plot);
                        loadJobsForPlot(plot.id);
                      }}
                    >
                      <div className="plot-card-header">
                        <span className="plot-name">{plot.name}</span>
                        <span className="plot-area">{plot.area_acres} acres</span>
                      </div>

                      <div className="plot-card-body">
                        <div className="plot-metric">
                          <span className="metric-label">Booked</span>
                          <span className="metric-value">{summary.bookedArea.toFixed(2)} ac</span>
                        </div>
                        <div className="plot-metric">
                          <span className="metric-label">Allocated</span>
                          <span className="metric-value">
                            {summary.allocatedArea.toFixed(2)} ac
                          </span>
                        </div>
                        <div className="plot-metric">
                          <span className="metric-label">Remaining</span>
                          <span className="metric-value">
                            {summary.remainingArea.toFixed(2)} ac
                          </span>
                        </div>
                      </div>

                      {plot.plot_code && (
                        <div className="plot-card-footer">
                          <span className="plot-code">{plot.plot_code}</span>
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <>
            <button
              className="btn-back"
              onClick={() => {
                setSelectedPlotId(null);
                setSelectedPlot(null);
                setSelectedJob(null);
              }}
            >
              ← Back to Plots
            </button>

            {activityRevenueRows.length > 0 && (
              <div className="activity-revenue-list">
                {activityRevenueRows.map((row) => (
                  <div
                    key={row.activityId}
                    className={`revenue-strip revenue-${row.status.toLowerCase()}`}
                  >
                    {row.status === 'GREEN' && (
                      <>
                        <span className="revenue-label">✅ {row.activityName} fully booked</span>
                        <span className="revenue-value">
                          ₹{row.bookedRevenue.toFixed(0)} on {row.bookedArea.toFixed(2)} ac
                        </span>
                      </>
                    )}

                    {row.status === 'YELLOW' && (
                      <>
                        <span className="revenue-label">
                          🟡 {row.activityName} partially booked
                        </span>
                        <span className="revenue-value">
                          Booked: ₹{row.bookedRevenue.toFixed(0)} ({row.bookedArea.toFixed(2)} /{' '}
                          {Number(selectedPlot?.area_acres).toFixed(2)} ac)
                        </span>
                        <span className="revenue-missed">
                          Potential on remaining {row.unbookedArea.toFixed(2)} ac: ₹
                          {row.potentialRevenue.toFixed(0)}
                        </span>
                        {row.potentialDate && (
                          <span className="revenue-date">
                            Possible date: {new Date(row.potentialDate).toLocaleDateString()}
                          </span>
                        )}
                      </>
                    )}

                    {row.status === 'RED' && (
                      <>
                        <span className="revenue-label">🔴 {row.activityName} not booked</span>
                        <span className="revenue-value">
                          Potential revenue at default rate (₹{row.clusterDefaultRate}/ac): ₹
                          {row.potentialRevenue.toFixed(0)} on{' '}
                          {Number(selectedPlot?.area_acres).toFixed(2)} ac
                        </span>
                        {row.potentialDate && (
                          <span className="revenue-date">
                            Possible date: {new Date(row.potentialDate).toLocaleDateString()}
                          </span>
                        )}
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}

            {!selectedJob ? (
              <div className="empty-state">
                <div className="empty-state-icon">📋</div>
                <p className="empty-state-text">No jobs for this plot yet</p>
              </div>
            ) : (
              <>
                <div className="job-detail-info">
                  <div className="info-row">
                    <span className="info-label">Job ID:</span>
                    <span className="info-value">{selectedJob.job_id}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Crop:</span>
                    <span className="info-value">
                      {(selectedJob as any).crop_name || 'Not specified'}
                    </span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Variety:</span>
                    <span className="info-value">{selectedJob.variety || 'Not specified'}</span>
                  </div>
                </div>

                <div className="activities-section">
                  <div className="section-header">
                    <h3 className="section-title">Activities</h3>
                    <button
                      onClick={() => setShowAddActivityModal(true)}
                      className="btn-secondary btn-sm"
                    >
                      <Plus size={14} /> Add Activity
                    </button>
                  </div>

                  {selectedJob.activities && selectedJob.activities.length > 0 ? (
                    <div className="activities-list">
                      {selectedJob.activities.map((activity: any) => (
                        <div key={activity.id} className="activity-card">
                          <div className="activity-header">
                            <div>
                              <span className="activity-name">{activity.activity_name}</span>
                              {activity.is_strict && <span className="strict-badge">STRICT</span>}
                            </div>
<button
          onClick={() => {
            setEditingActivity(activity);
            setShowEditActivityModal(true);
          }}
          className="icon-btn edit"
          title="Edit"
        >
          <Edit size={14} />
        </button>
        <button
          onClick={() => handleDeleteActivity(activity.id)}
          className="icon-btn danger"
          title="Delete"
        >
          <Trash2 size={14}/>
          </button>
                          </div>

                          <div className="activity-details">
                            <div className="detail-grid">
                              <div className="detail-item">
                                <label>Total Area</label>
                                <span>{activity.total_area} acres</span>
                              </div>
                              <div className="detail-item">
                                <label>Allocated</label>
                                <span>{activity.allocated_area} acres</span>
                              </div>
                              <div className="detail-item">
                                <label>Remaining</label>
                                <span className="remaining-value">
                                  {activity.remaining_area} acres
                                </span>
                              </div>
                              <div className="detail-item">
                                <label>Rate</label>
                                <span>₹{activity.rate_per_acre}/acre</span>
                              </div>
                            </div>
                            {/* Edit Activity Modal */}
{showEditActivityModal && editingActivity && (
  <div className="modal-overlay" onClick={() => setShowEditActivityModal(false)}>
    <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
      <div className="modal-header">
        <h3 className="modal-title">Edit Activity</h3>
        <button onClick={() => setShowEditActivityModal(false)} className="modal-close">
          <X size={20} />
        </button>
      </div>

      <div className="modal-body">
        {/* Activity Name (Read-only) */}
        <div className="form-group">
          <label className="form-label">Activity</label>
          <input
            type="text"
            value={editingActivity.activity_name}
            className="form-input"
            disabled
            style={{ backgroundColor: '#f3f4f6', cursor: 'not-allowed' }}
          />
        </div>

        {/* Total Area */}
        <div className="form-group">
          <label className="form-label">Total Area (acres) *</label>
          <input
            type="number"
            step="0.01"
            value={editingActivity.total_area}
            onChange={(e) => {
              const val = parseFloat(e.target.value) || 0;
              setEditingActivity({ ...editingActivity, total_area: val });
            }}
            className="form-input"
            required
          />
          <small className="form-help" style={{ color: '#6b7280' }}>
            Already allocated: {editingActivity.allocated_area} acres
            <br />
            {editingActivity.total_area < editingActivity.allocated_area && (
              <span style={{ color: '#dc2626' }}>
                ⚠️ Cannot be less than allocated area
              </span>
            )}
          </small>
        </div>

        {/* Rate */}
        <div className="form-group">
          <label className="form-label">Rate (₹/acre) *</label>
          <input
            type="number"
            step="0.01"
            value={editingActivity.rate_per_acre}
            onChange={(e) =>
              setEditingActivity({
                ...editingActivity,
                rate_per_acre: parseFloat(e.target.value) || 0,
              })
            }
            className="form-input"
            required
          />
        </div>

        {/* Scheduled Date */}
        <div className="form-group">
          <label className="form-label">Scheduled Date</label>
          <input
            type="date"
            value={editingActivity.scheduled_date || ''}
            onChange={(e) =>
              setEditingActivity({ ...editingActivity, scheduled_date: e.target.value })
            }
            className="form-input"
          />
        </div>

        {/* Strict Checkbox */}
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={editingActivity.is_strict}
              onChange={(e) =>
                setEditingActivity({ ...editingActivity, is_strict: e.target.checked })
              }
            />
            <span>Strict (cannot split)</span>
          </label>
        </div>
      </div>

      <div className="modal-footer">
        <button
          onClick={() => {
            setShowEditActivityModal(false);
            setEditingActivity(null);
          }}
          className="btn-secondary"
        >
          Cancel
        </button>
        <button
          onClick={handleEditActivity}
          className="btn-primary"
          disabled={editingActivity.total_area < editingActivity.allocated_area}
        >
          Save Changes
        </button>
      </div>
    </div>
  </div>
)}

                            {activity.scheduled_date && (
                              <div className="scheduled-date">
                                📅 {new Date(activity.scheduled_date).toLocaleDateString()}
                              </div>
                            )}

                            <div className="progress-bar">
                              <div
                                className="progress-fill"
                                style={{
                                  width: `${
                                    (activity.allocated_area / activity.total_area) * 100
                                  }%`,
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="empty-text">No activities added yet</p>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Create Job Modal */}
      {showAddJobModal && (
        <div className="modal-overlay" onClick={() => setShowAddJobModal(false)}>
          <div className="modal-content modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Create New Job</h3>
              <button onClick={() => setShowAddJobModal(false)} className="modal-close">
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              {/* Farmer section */}
              {!selectedFarmerId ? (
                <>
                  <div className="form-group">
                    <label className="form-label">Farmer Selection</label>
                    <div className="radio-group">
                      <label className="radio-label">
                        <input
                          type="radio"
                          name="farmerType"
                          checked={!isNewFarmer}
                          onChange={() => setIsNewFarmer(false)}
                        />
                        <span>Existing Farmer</span>
                      </label>
                      <label className="radio-label">
                        <input
                          type="radio"
                          name="farmerType"
                          checked={isNewFarmer}
                          onChange={() => setIsNewFarmer(true)}
                        />
                        <span>New Farmer</span>
                      </label>
                    </div>
                  </div>

                  {!isNewFarmer && (
                    <div className="form-group">
                      <label className="form-label">Select Farmer *</label>
                      <select
                        value={newJob.farmer_id}
                        onChange={(e) => {
                          const f = farmers.find((x) => x.farmer_id === e.target.value);
                          setNewJob({
                            ...newJob,
                            farmer_id: e.target.value,
                            farmer_name: f?.farmer_name || '',
                            mobile_number: f?.phone_number || '',
                          });
                          if (f) loadFarmerPlots(f.farmer_id);
                        }}
                        className="form-select"
                        required={!isNewFarmer}
                      >
                        <option value="">Select farmer</option>
                        {farmers.map((f) => (
                          <option key={f.farmer_id} value={f.farmer_id}>
                            {f.farmer_name} - {f.phone_number}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {isNewFarmer && (
                    <>
                      <div className="form-group">
                        <label className="form-label">Farmer Name *</label>
                        <input
                          type="text"
                          value={newJob.farmer_name}
                          onChange={(e) => setNewJob({ ...newJob, farmer_name: e.target.value })}
                          className="form-input"
                          required
                        />
                      </div>
                      <div className="form-group">
  <label className="form-label">Mobile Number</label>

  <input
    type="tel"
    inputMode="numeric"
    maxLength={10}
    value={newJob.mobile_number}
    onChange={(e) => {
      const value = e.target.value.replace(/\D/g, ""); // remove non-digits

      if (value.length <= 10) {
        setNewJob({
          ...newJob,
          mobile_number: value,
        });
      }
    }}
    className="form-input"
    placeholder="9876543210"
  />
</div>

                    </>
                  )}
                </>
              ) : (
                <>
                  <div className="form-group">
                    <label className="form-label">Farmer for this job</label>
                    <div className="radio-group">
                      <label className="radio-label">
                        <input
                          type="radio"
                          name="farmerModeSelected"
                          checked={!isNewFarmer}
                          onChange={() => setIsNewFarmer(false)}
                        />
                        <span>Use selected farmer ({selectedFarmerName})</span>
                      </label>
                      <label className="radio-label">
                        <input
                          type="radio"
                          name="farmerModeSelected"
                          checked={isNewFarmer}
                          onChange={() => {
                            setIsNewFarmer(true);
                            setNewJob({
                              ...newJob,
                              farmer_id: '',
                              farmer_name: '',
                              mobile_number: '',
                            });
                          }}
                        />
                        <span>Create new farmer</span>
                      </label>
                    </div>
                  </div>

                  {!isNewFarmer && clusterInfo && (
                    <div className="location-info">
                      <p>
                        <strong>Farmer:</strong> {selectedFarmerName}
                      </p>
                      <p>
                        <strong>Location:</strong> {clusterInfo.village}, {clusterInfo.taluka},{' '}
                        {clusterInfo.district}
                      </p>
                    </div>
                  )}

                  {isNewFarmer && (
                    <>
                      <div className="form-group">
                        <label className="form-label">New Farmer Name *</label>
                        <input
                          type="text"
                          value={newJob.farmer_name}
                          onChange={(e) => setNewJob({ ...newJob, farmer_name: e.target.value })}
                          className="form-input"
                          required
                        />
                      </div>
                      <div className="form-group">
  <label className="form-label">Mobile Number</label>

  <input
    type="tel"
    inputMode="numeric"
    maxLength={10}
    value={newJob.mobile_number}
    onChange={(e) => {
      const value = e.target.value.replace(/\D/g, ""); // remove non-digits

      if (value.length <= 10) {
        setNewJob({
          ...newJob,
          mobile_number: value,
        });
      }
    }}
    className="form-input"
    placeholder="9876543210"
  />
</div>

                    </>
                  )}
                </>
              )}

              {/* Plot Selection */}
              <div className="form-divider">Plot Selection</div>

              <div className="form-group">
                <label className="form-label">Use Existing Plot or Create New?</label>
                <div className="radio-group">
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="plotMode"
                      checked={plotMode === 'existing'}
                      onChange={() => setPlotMode('existing')}
                      disabled={isNewFarmer}
                    />
                    <span>Existing Plot</span>
                  </label>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="plotMode"
                      checked={plotMode === 'new'}
                      onChange={() => setPlotMode('new')}
                    />
                    <span>New Plot</span>
                  </label>
                </div>
              </div>

              {/* Existing plot dropdown */}
              {plotMode === 'existing' && !isNewFarmer && (
                <div className="form-group">
                  <label className="form-label">Select Plot *</label>
                  <select
                    className="form-select"
                    value={selectedPlotId ?? ''}
                    onChange={(e) => {
                      const id = e.target.value ? Number(e.target.value) : null;
                      const plot = farmerPlots.find((p) => p.id === id) || null;
                      setSelectedPlotId(id);
                      setSelectedPlot(plot);
                      if (plot) {
                        const plotArea = Number(plot.area_acres || 0);
                        loadPlotActivityStatus(id!, plotArea);
                      }
                    }}
                    disabled={farmerPlots.length === 0}
                  >
                    <option value="">Choose a plot</option>
                    {farmerPlots.map((plot) => (
                      <option key={plot.id} value={plot.id}>
                        {plot.name} ({plot.area_acres} ac)
                      </option>
                    ))}
                  </select>
                  {farmerPlots.length === 0 && (
                    <small className="form-help">
                      This farmer has no plots yet. Switch to "New Plot" to create one.
                    </small>
                  )}
                </div>
              )}

              {/* New Plot Details */}
              {(plotMode === 'new' || isNewFarmer) && (
                <>
                  <div className="form-divider">New Plot Details</div>
                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Plot Name</label>
                      <input
                        type="text"
                        value={newPlot.name}
                        onChange={(e) => setNewPlot({ ...newPlot, name: e.target.value })}
                        className="form-input"
                        placeholder="Plot 1"
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Plot Size (acres) *</label>
                      <input
                        type="number"
                        step="0.01"
                        value={newPlot.area_acres}
                        onChange={(e) => handleNewPlotAreaChange(parseFloat(e.target.value) || 0)}
                        className="form-input"
                        required
                      />
                    </div>
                    {/* <div className="form-group">
                      <label className="form-label">Plot Code</label>
                      <input
                        type="text"
                        value={newPlot.plot_code}
                        onChange={(e) => setNewPlot({ ...newPlot, plot_code: e.target.value })}
                        className="form-input"
                        placeholder="Optional"
                      />
                    </div> */}
                  </div>
                </>
              )}

              {/* Crop Details */}
              <div className="form-divider">Crop Details</div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Crop Name</label>
                  <input
                    type="text"
                    value={newJob.crop_name}
                    onChange={(e) => setNewJob({ ...newJob, crop_name: e.target.value })}
                    className="form-input"
                    placeholder="Grapes"
                    readOnly={plotMode === 'existing' && selectedPlotId !== null}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Variety</label>
                  <input
                    type="text"
                    value={newJob.variety}
                    onChange={(e) => setNewJob({ ...newJob, variety: e.target.value })}
                    className="form-input"
                    placeholder="ARA15, Crimson"
                    readOnly={plotMode === 'existing' && selectedPlotId !== null}
                  />
                </div>
              </div>

              {/* Show Booked and Not-Booked Activities for Existing Plot */}
              {plotMode === 'existing' && selectedPlotId !== null && (
                <>
                  {/* Booked Activities */}
                  {bookedActivities.length > 0 && (
                    <>
                      <div className="form-divider">✅ Already Booked Activities (Read-only)</div>
                      <div className="booked-activities-list">
                        {bookedActivities.map((activity, index) => (
                          <div key={index} className="booked-activity-row">
                            <div className="activity-info">
                              <span className="activity-name">{activity.activity_name}</span>
                              {activity.is_strict && <span className="strict-badge-sm">STRICT</span>}
                            </div>
                            <div className="activity-stats">
                              <span>{activity.total_area} ac</span>
                              <span>₹{activity.rate_per_acre}/ac</span>
                              <span>
                                {activity.scheduled_date
                                  ? new Date(activity.scheduled_date).toLocaleDateString()
                                  : 'No date'}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {/* Not-Booked Activities */}
                  {notBookedActivities.length > 0 && (
                    <>
                      <div className="form-divider">
                        ❌ Not Booked Activities (Select to add to job)
                      </div>
                      <div className="not-booked-activities-list">
                        {notBookedActivities.map((activity, index) => (
                          <div key={index} className="not-booked-activity-row">
                            <div className="activity-checkbox-header">
                              <label className="checkbox-label">
                                <input
                                  type="checkbox"
                                  checked={activity.selected}
                                  onChange={(e) => {
                                    const updated = [...notBookedActivities];
                                    updated[index].selected = e.target.checked;
                                    setNotBookedActivities(updated);
                                    recalcBookingAmountFromNotBooked();
                                  }}
                                />
                                <span className="activity-name">{activity.activity_name}</span>
                              </label>
                              <label className="checkbox-label strict-toggle-sm">
                                <input
                                  type="checkbox"
                                  checked={!!activity.is_strict}
                                  onChange={(e) => {
                                    const updated = [...notBookedActivities];
                                    updated[index].is_strict = e.target.checked;
                                    setNotBookedActivities(updated);
                                  }}
                                />
                                <span>Strict</span>
                              </label>
                            </div>

                            {activity.selected && (
                              <div className="activity-edit-fields">
                                <div className="form-group-inline">
                                  <label>Area (acres)</label>
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={activity.total_area}
                                    onChange={(e) => {
                                      const val = parseFloat(e.target.value) || 0;
                                      const plotArea = Number(selectedPlot?.area_acres || 0);
                                      if (plotArea > 0 && val > plotArea) {
                                        toast.error(
                                          `Area cannot exceed plot size (${plotArea} acres)`
                                        );
                                        return;
                                      }
                                      const updated = [...notBookedActivities];
                                      updated[index].total_area = val;
                                      setNotBookedActivities(updated);
                                      recalcBookingAmountFromNotBooked();
                                    }}
                                    className="form-input-sm"
                                  />
                                </div>

                                <div className="form-group-inline">
                                  <label>Rate (₹/ac)</label>
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={activity.rate_per_acre}
                                    onChange={(e) => {
                                      const updated = [...notBookedActivities];
                                      updated[index].rate_per_acre =
                                        parseFloat(e.target.value) || 0;
                                      setNotBookedActivities(updated);
                                      recalcBookingAmountFromNotBooked();
                                    }}
                                    className="form-input-sm"
                                  />
                                </div>

                                <div className="form-group-inline">
                                  <label>Date</label>
                                  <input
                                    type="date"
                                    value={activity.scheduled_date}
                                    onChange={(e) => {
                                      const updated = [...notBookedActivities];
                                      updated[index].scheduled_date = e.target.value;
                                      setNotBookedActivities(updated);
                                    }}
                                    className="form-input-sm"
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {notBookedActivities.length === 0 && bookedActivities.length > 0 && (
                    <div className="info-message">
                      ℹ️ All activities from the catalog are already booked for this plot.
                    </div>
                  )}
                </>
              )}

              {/* Base Activity Date - Only for New Plot */}
              {(plotMode === 'new' || isNewFarmer) && (
                <>
                  <div className="form-group">
                    <label className="form-label">First Activity Date (Base Date) *</label>
                    <input
                      type="date"
                      value={newJob.base_date}
                      onChange={(e) => handleBaseDateChange(e.target.value)}
                      className="form-input"
                      required
                    />
                    <small className="form-help">
                      All activity dates will auto-calculate from this date
                    </small>
                  </div>

                  {/* Auto-filled Activities for New Plot */}
                  {autoFilledActivities.length > 0 && (
                    <>
                      <div className="form-divider">
                        Activities (auto-filled from cluster calendar)
                      </div>
                      <div className="activity-checklist">
                        {autoFilledActivities.map((a, index) => (
                          <div
                            key={index}
                            className={`activity-check-row ${!a.enabled ? 'disabled' : ''}`}
                          >
                            <div className="activity-check-header">
                              <label className="checkbox-label">
                                <input
                                  type="checkbox"
                                  checked={a.enabled}
                                  onChange={(e) => {
                                    const updated = [...autoFilledActivities];
                                    updated[index].enabled = e.target.checked;
                                    setAutoFilledActivities(updated);
                                    recalcBookingAmount(updated.filter((x) => x.enabled));
                                  }}
                                />
                                <span className="activity-check-name">{a.activity_name}</span>
                              </label>

                              <label className="checkbox-label strict-toggle-sm">
                                <input
                                  type="checkbox"
                                  checked={!!a.is_strict}
                                  onChange={(e) => {
                                    const updated = [...autoFilledActivities];
                                    updated[index].is_strict = e.target.checked;
                                    setAutoFilledActivities(updated);
                                  }}
                                />
                                <span>Strict</span>
                              </label>
                            </div>

                            {a.enabled && (
                              <div className="activity-check-details">
                                <div className="form-group-inline">
                                  <label>Area (acres)</label>
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={a.total_area}
                                    onChange={(e) => {
                                      const val = parseFloat(e.target.value) || 0;
                                      if (newPlot.area_acres > 0 && val > newPlot.area_acres) {
                                        toast.error(
                                          `Area cannot exceed plot size (${newPlot.area_acres} acres)`
                                        );
                                        return;
                                      }
                                      const updated = [...autoFilledActivities];
                                      updated[index].total_area = val;
                                      setAutoFilledActivities(updated);
                                      recalcBookingAmount(updated.filter((x) => x.enabled));
                                    }}
                                    className="form-input-sm"
                                  />
                                </div>

                                <div className="form-group-inline">
                                  <label>Rate (₹/ac)</label>
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={a.rate_per_acre}
                                    onChange={(e) => {
                                      const updated = [...autoFilledActivities];
                                      updated[index].rate_per_acre =
                                        parseFloat(e.target.value) || 0;
                                      setAutoFilledActivities(updated);
                                      recalcBookingAmount(updated.filter((x) => x.enabled));
                                    }}
                                    className="form-input-sm"
                                  />
                                </div>

                                <div className="form-group-inline">
                                  <label>Date</label>
                                  <input
                                    type="date"
                                    value={a.scheduled_date}
                                    onChange={(e) => {
                                      const updated = [...autoFilledActivities];
                                      updated[index].scheduled_date = e.target.value;
                                      setAutoFilledActivities(updated);
                                    }}
                                    className="form-input-sm"
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}

              {/* Booking Summary */}
              {((plotMode === 'new' || isNewFarmer) && autoFilledActivities.length > 0) ||
                (plotMode === 'existing' && notBookedActivities.some((a) => a.selected)) ? (
                <div className="booking-summary">
                  <div className="summary-row">
                    <span className="summary-label">Total Booking Amount:</span>
                    <span className="summary-value">₹{newJob.booking_amount.toFixed(2)}</span>
                  </div>
                  <div className="summary-row">
                    <span className="summary-label">Payment Status:</span>
                    <select
                      value={newJob.payment_status}
                      onChange={(e) => setNewJob({ ...newJob, payment_status: e.target.value })}
                      className="form-select-sm"
                    >
                      <option value="pending">Pending</option>
                      <option value="partial">Partial</option>
                      <option value="paid">Paid</option>
                    </select>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="modal-footer">
              <button onClick={() => setShowAddJobModal(false)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={handleCreateJob}
                className="btn-primary"
                disabled={
                  plotMode === 'new'
                    ? !newPlot.area_acres || !newJob.base_date
                    : !selectedPlotId || !notBookedActivities.some((a) => a.selected)
                }
              >
                Create Job
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Activity Modal */}
      {showAddActivityModal && selectedJob && (
        <div className="modal-overlay" onClick={() => setShowAddActivityModal(false)}>
          <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Add Activity</h3>
              <button onClick={() => setShowAddActivityModal(false)} className="modal-close">
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Activity *</label>
                <select
                  value={newActivity.activity_id}
                  onChange={(e) => {
                    const actId = parseInt(e.target.value);
                    const selectedAct = clusterCalendar.find((a) => a.activity_id === actId);
                    setNewActivity({
                      ...newActivity,
                      activity_id: actId,
                      rate_per_acre: selectedAct?.rate_per_acre || 0,
                    });
                  }}
                  className="form-select"
                >
                  <option value={0}>Select activity</option>
                  {clusterCalendar.map((act) => (
                    <option key={act.activity_id} value={act.activity_id}>
                      {act.activity_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Total Area (acres) *</label>
                <input
                  type="number"
                  step="0.01"
                  value={newActivity.total_area}
                  onChange={(e) =>
                    setNewActivity({ ...newActivity, total_area: parseFloat(e.target.value) })
                  }
                  className="form-input"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Rate (₹/acre)</label>
                <input
                  type="number"
                  step="0.01"
                  value={newActivity.rate_per_acre}
                  onChange={(e) =>
                    setNewActivity({ ...newActivity, rate_per_acre: parseFloat(e.target.value) })
                  }
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Scheduled Date</label>
                <input
                  type="date"
                  value={newActivity.scheduled_date}
                  onChange={(e) =>
                    setNewActivity({ ...newActivity, scheduled_date: e.target.value })
                  }
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={newActivity.is_strict}
                    onChange={(e) =>
                      setNewActivity({ ...newActivity, is_strict: e.target.checked })
                    }
                  />
                  <span>Strict (cannot split)</span>
                </label>
              </div>
            </div>

            <div className="modal-footer">
              <button onClick={() => setShowAddActivityModal(false)} className="btn-secondary">
                Cancel
              </button>
              <button onClick={handleAddActivity} className="btn-primary">
                Add Activity
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default JobDetailPanel;