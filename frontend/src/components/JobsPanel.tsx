// components/JobsPanel.tsx
import React, { useState, useMemo, useEffect, useRef } from 'react';
import { Plus,MapPin, ChevronDown, ChevronUp, Edit, Trash2, X,Phone } from 'lucide-react';
import toast from 'react-hot-toast';
import { Job } from '../types/types';
import { API_BASE_URL } from '@/types/config';
import './job.css';
import Dialpad from '@/call';

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
  doneCount: number;
  remainingArea: number;
  nearestDate: string | null;
  mobileNumber: string;
  poc: string;
  jobs: Job[];

  totalAcres: number;   // ✅ new
}

const JobsPanel: React.FC<JobsPanelProps> = ({
  jobs,
  loading,
  onRefresh,
  onFarmerSelect,
  clusterId,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedFarmerId, setExpandedFarmerId] = useState<string | null>(null);
  const [expandedPlotId, setExpandedPlotId] = useState<number | null>(null);

  // Per-farmer expanded data
  const [farmerPlots, setFarmerPlots] = useState<Record<string, any[]>>({});
  const [plotJobs, setPlotJobs] = useState<Record<number, Job[]>>({});

  // Add job modal state (inline)
  const [showAddJob, setShowAddJob] = useState<string | null>(null); // farmerId
  const [allActivities, setAllActivities] = useState<any[]>([]);
  const [clusterCalendar, setClusterCalendar] = useState<any[]>([]);
  const [farmers, setFarmers] = useState<any[]>([]);

  // Edit activity
  const [editingActivity, setEditingActivity] = useState<any>(null);

  // New job form
  const [newJob, setNewJob] = useState({
    farmer_name: '',
    mobile_number: '',
    crop_name: '',
    variety: '',
    booking_amount: 0,
    payment_status: 'pending',
    base_date: '',
  });
  const [newPlot, setNewPlot] = useState({ name: '', area_acres: 0 });
  const [autoFilledActivities, setAutoFilledActivities] = useState<any[]>([]);
  const [isNewFarmer, setIsNewFarmer] = useState(true);
  const [plotMode, setPlotMode] = useState<'existing' | 'new'>('new');
  const [selectedNewPlotId, setSelectedNewPlotId] = useState<number | null>(null);
  const [bookedActivities, setBookedActivities] = useState<any[]>([]);
  const [notBookedActivities, setNotBookedActivities] = useState<any[]>([]);

  // Show add job modal (top-level new farmer)
  const [showNewFarmerModal, setShowNewFarmerModal] = useState(false);

  useEffect(() => {
    loadClusterCalendar();
    loadAllActivities();
    loadFarmers();
  }, [clusterId]);

  const loadClusterCalendar = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/clusters/${clusterId}/activity-calendar/`);
      const data = await res.json();
      setClusterCalendar(data.activities || []);
    } catch (e) { console.error(e); }
  };

  const loadAllActivities = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/activities/`);
      const data = await res.json();
      setAllActivities(data);
    } catch (e) { console.error(e); }
  };

  const loadFarmers = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/farmers/?cluster_id=${clusterId}`);
      const data = await res.json();
      setFarmers(data);
    } catch (e) { console.error(e); }
  };

  const [farmerAcresMap, setFarmerAcresMap] = useState<Record<string, number>>({});

useEffect(() => {
  const fetchFarmerAcres = async () => {
    const res = await fetch(`${API_BASE_URL}/api/farmers/?cluster_id=${clusterId}`);
    const data = await res.json();
    const map: Record<string, number> = {};
    data.forEach((f: any) => {
      map[f.farmer_id] = Number(f.total_acres) || 0;
    });
    setFarmerAcresMap(map);
  };
  fetchFarmerAcres();
}, [clusterId]);

  const loadFarmerPlots = async (farmerId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/plots/?farmer_id=${farmerId}&cluster_id=${clusterId}`);
      const data = await res.json();
      setFarmerPlots(prev => ({ ...prev, [farmerId]: data }));
      return data;
    } catch (e) { return []; }
  };

const loadPlotJobs = async (plotId: number) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/jobs/?plot=${plotId}`);
      const data = await res.json();
      
      // ✅ Filter activities to only this plot's
      const filtered = data.map((job: any) => ({
        ...job,
        activities: (job.activities || []).filter(
          (a: any) => Number(a.plot) === Number(plotId) || Number(a.plot_id) === Number(plotId)
        )
      }));
      
      setPlotJobs(prev => ({ ...prev, [plotId]: filtered }));
      return filtered;
    } catch (e) { return []; }
};

  const loadPlotActivityStatus = async (plotId: number, plotArea: number, farmerId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/jobs/?cluster_id=${clusterId}&plot=${plotId}`);
      const jobs = await res.json();
      const booked: any[] = [];
      const bookedIds = new Set<number>();
      jobs.forEach((job: any) => {
        (job.activities || []).forEach((a: any) => {
          booked.push(a);
          bookedIds.add(a.activity_id);
        });
      });
      setBookedActivities(booked);
      const notBooked = allActivities.filter(a => !bookedIds.has(a.id)).map(a => ({
        activity_id: a.id,
        activity_name: a.name,
        is_strict: a.is_strict,
        selected: false,
        total_area: plotArea,
        rate_per_acre: Number(a.default_rate_per_acre || 0),
        scheduled_date: '',
      }));
      setNotBookedActivities(notBooked);
    } catch (e) { console.error(e); }
  };

  const autoFillFromCalendar = (area: number, baseDate: string) => {
    const base = new Date(baseDate);
    const filled = clusterCalendar.map((cal, idx) => {
      const d = new Date(base);
      d.setDate(d.getDate() + (idx === 0 ? 0 : cal.gap_days));
      return {
        activity_id: cal.activity_id,
        activity_name: cal.activity_name,
        total_area: area,
        rate_per_acre: cal.rate_per_acre,
        is_strict: cal.is_strict,
        scheduled_date: d.toISOString().split('T')[0],
        enabled: true,
      };
    });
    setAutoFilledActivities(filled);
    recalcAmount(filled.filter(a => a.enabled));
  };

  const recalcAmount = (list: any[]) => {
    const total = list.reduce((s, a) => s + (a.total_area || 0) * (a.rate_per_acre || 0), 0);
    setNewJob(prev => ({ ...prev, booking_amount: total }));
  };

  const recalcFromNotBooked = (list: any[]) => {
    const total = list.filter(a => a.selected).reduce((s, a) => s + a.total_area * a.rate_per_acre, 0);
    setNewJob(prev => ({ ...prev, booking_amount: total }));
  };

  const handleFarmerClick = async (farmerId: string, farmerName: string) => {
    if (expandedFarmerId === farmerId) {
      setExpandedFarmerId(null);
      setExpandedPlotId(null);
      return;
    }
    setExpandedFarmerId(farmerId);
    setExpandedPlotId(null);
    onFarmerSelect(farmerId, farmerName);
    if (!farmerPlots[farmerId]) {
      await loadFarmerPlots(farmerId);
    }
  };

const handlePlotClick = async (plotId: number, plotArea: number, farmerId: string) => {
    if (expandedPlotId === plotId) {
      setExpandedPlotId(null);
      return;
    }
    setExpandedPlotId(plotId);
    await loadPlotJobs(plotId);  // ✅ always reload, remove the if(!plotJobs[plotId]) check
};


  const handleEditActivity = async () => {
    if (!editingActivity) return;
    if (editingActivity.total_area < editingActivity.allocated_area) {
      toast.error(`Cannot be less than allocated area (${editingActivity.allocated_area} ac)`);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/job-activities/${editingActivity.id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          total_area: editingActivity.total_area,
          rate_per_acre: editingActivity.rate_per_acre,
          scheduled_date: editingActivity.scheduled_date,
          is_strict: editingActivity.is_strict,
        }),
      });
      if (res.ok) {
        toast.success('Updated!');
        setEditingActivity(null);
        await loadPlotJobs(editingActivity.plotId);
        onRefresh();
        window.location.reload();
      } else {
        const err = await res.json();
        toast.error(err.error || 'Failed');
      }
    } catch (e) { toast.error('Failed'); }
  };

  const resetJobForm = () => {
    setNewJob({ farmer_name: '', mobile_number: '', crop_name: '', variety: '', booking_amount: 0, payment_status: 'pending', base_date: '' });
    setNewPlot({ name: '', area_acres: 0 });
    setAutoFilledActivities([]);
    setBookedActivities([]);
    setNotBookedActivities([]);
    setSelectedNewPlotId(null);
    setPlotMode('new');
    setIsNewFarmer(true);
  };

  const handleCreateJob = async (targetFarmerId?: string) => {
    try {
      let farmerId = targetFarmerId || '';

      if (!farmerId || isNewFarmer) {
        if (!newJob.farmer_name.trim()) { toast.error('Enter farmer name'); return; }
        const res = await fetch(`${API_BASE_URL}/api/farmers/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            farmer_id: `F${Date.now()}`,
            farmer_name: newJob.farmer_name,
            phone_number: newJob.mobile_number,
            cluster: clusterId,
          }),
        });
        if (!res.ok) throw new Error('Failed to create farmer');
        const f = await res.json();
        farmerId = f.farmer_id;

        window.location.reload();
      }

      let plotId: number | null = null;

      if (plotMode === 'existing' && selectedNewPlotId) {
        plotId = selectedNewPlotId;
      } else {
        if (newPlot.area_acres <= 0) { toast.error('Enter plot size'); return; }
        const res = await fetch(`${API_BASE_URL}/api/plots/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            farmer: farmerId,
            cluster: clusterId,
            name: newPlot.name || `Plot ${Date.now()}`,
            area_acres: newPlot.area_acres,
            plot_code: `P${Date.now()}`,
          }),
        });
        if (!res.ok) throw new Error('Failed to create plot');
        const p = await res.json();
        plotId = p.id;

        window.location.reload();
      }

      if (!plotId) { toast.error('Could not determine plot'); return; }

      let activitiesToCreate: any[] = [];
      if (plotMode === 'existing' && selectedNewPlotId) {
        activitiesToCreate = notBookedActivities.filter(a => a.selected).map(a => ({
          activity_id: a.activity_id,
          total_area: a.total_area,
          rate_per_acre: a.rate_per_acre,
          is_strict: a.is_strict,
          scheduled_date: a.scheduled_date || null,
        }));
        if (!activitiesToCreate.length) { toast.error('Select at least one activity'); return; }
      } else {
        activitiesToCreate = autoFilledActivities.filter(a => a.enabled).map(a => ({
          activity_id: a.activity_id,
          total_area: a.total_area,
          rate_per_acre: a.rate_per_acre,
          is_strict: a.is_strict,
          scheduled_date: a.scheduled_date || null,
        }));
      }

      const jobRes = await fetch(`${API_BASE_URL}/api/jobs/`, {
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
          cluster: clusterId,
          booking_amount: newJob.booking_amount,
          payment_status: newJob.payment_status,
        }),
      });
      if (!jobRes.ok) throw new Error('Failed to create job');
      window.location.reload();
      const jobData = await jobRes.json();

      for (const a of activitiesToCreate) {
        if (!a.activity_id || a.total_area <= 0) continue;
        await fetch(`${API_BASE_URL}/api/jobs/${jobData.job_id}/add_activity/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...a, plot: plotId }),
        });
      }

      toast.success('Job created!');
      setShowAddJob(null);
      setShowNewFarmerModal(false);
      resetJobForm();
      window.location.reload();
      await loadFarmerPlots(farmerId);
      if (expandedFarmerId === farmerId && plotId) {
        await loadPlotJobs(plotId);
      }
      onRefresh();
    } catch (e) {
      toast.error('Failed to create job');
      console.error(e);
    }
  };

const [dialpadOpen, setDialpadOpen] = useState(false);
const [dialpadNumber, setDialpadNumber] = useState('');
  // Add to your component state
const [mukkadamOptions, setMukkadamOptions] = useState<{id: number; name: string; crew_size: number}[]>([]);
const [farmerMukkadamMap, setFarmerMukkadamMap] = useState<Record<string, {id: number; name: string} | null>>({});
const [assigningFarmerId, setAssigningFarmerId] = useState<string | null>(null);


// In handleAssignMukkadam, after successful assignment:
const handleAssignMukkadam = async (farmerId: string, mukkadamId: number) => {
  setAssigningFarmerId(farmerId);
  try {
    const res = await fetch(`${API_BASE_URL}/api/cluster/${clusterId}/assign-primary-mukkadam/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ farmer_id: farmerId, mukkadam_id: mukkadamId }),
    });
    const data = await res.json();
    if (res.ok) {
      setFarmerMukkadamMap(prev => ({
        ...prev,
        [farmerId]: { id: data.mukkadam_id, name: data.mukkadam_name },
      }));



      // ── Trigger auto-allocation after assignment ──
      fetch(`${API_BASE_URL}/api/cluster/${clusterId}/auto-allocate/`, {
        method: 'POST',
      })
        .then(r => r.json())
        .then(result => {
          // Refresh allocations so calendar updates
          if (result.allocated_count > 0 && onRefresh) onRefresh();
          window.location.reload();
        })
        .catch(() => {});
    }
  } finally {
    setAssigningFarmerId(null);
  }
};
  // Build farmer summaries
const farmerSummaries = useMemo<FarmerSummary[]>(() => {
  if (!jobs || jobs.length === 0) return [];
  const todayStr = new Date().toISOString().split('T')[0];
  const filtered = jobs.filter(job =>
    job.farmer_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const map = new Map<string, FarmerSummary>();

  filtered.forEach(job => {
    const jobTotalAcres = (job as any).farmer?.total_acres ?? (job as any).farmer_total_acres ?? 0;

    if (!map.has(job.farmer_id)) {
      map.set(job.farmer_id, { 
        
  farmerId: job.farmer_id, farmerName: job.farmer_name, plotCount: 0, totalAcres: Number(farmerAcresMap[job.farmer_id]) || 0,
  totalActivities: 0, remainingArea: 0, doneCount: 0, nearestDate: null, jobs: [],
  // AFTER — read from farmers state which has phone_number
mobileNumber: (() => {
  const farmerData = farmers.find((f: any) => f.farmer_id === job.farmer_id);
  const raw = farmerData?.phone_number || '';
  const str = String(raw);
  return str.startsWith('91') && str.length === 12 ? str.slice(2) : str;
})(),

  poc: (job as any).point_of_contact || '',
});
    }
    const s = map.get(job.farmer_id)!;
    s.jobs.push(job);

    const activities = job.activities || [];
    
    // Step 1: Find the absolute nearest future date for this farmer
    activities.forEach((a: any) => {
      if (a.scheduled_date && a.scheduled_date >= todayStr) {
        if (!s.nearestDate || a.scheduled_date < s.nearestDate) {
          s.nearestDate = a.scheduled_date;
        }
      }
    });

    // Step 2: Calculate Remaining Area (Backlog + Next Activity)
    activities.forEach((a: any) => {
      s.totalActivities += 1;
      const isFullyAllocated = Number(a.allocated_area) >= Number(a.total_area);
      const isPast = a.scheduled_date < todayStr;
      const isNextActivity = a.scheduled_date === s.nearestDate;

      // Logic: Add to remaining if it's a past unallocated job OR the next upcoming job
      if (!isFullyAllocated && (isPast || isNextActivity || a.scheduled_date === todayStr)) {
        s.remainingArea += (Number(a.total_area) - Number(a.allocated_area));
      }

      // Done count logic
      if ((isPast || a.scheduled_date === todayStr) && isFullyAllocated) {
        s.doneCount += 1;
      }
    });
  });

  // Plot count calculation and Sorting
map.forEach(s => {
  const plots = new Set<number>();
  s.jobs.forEach(j => {
    (j.activities || []).forEach((act: any) => {
      if (act.plot) plots.add(Number(act.plot));
    });
  });
  s.plotCount = plots.size;
});




// Inside farmerSummaries useMemo sort function
return Array.from(map.values()).sort((a, b) => {
  // 1. Prioritize farmers with a next/backlog date
  if (a.nearestDate && !b.nearestDate) return -1;
  if (!a.nearestDate && b.nearestDate) return 1;
  
  // 2. If both have dates, sort by earliest date (nearest first)
  if (a.nearestDate !== b.nearestDate) {
    return (a.nearestDate || '') < (b.nearestDate || '') ? -1 : 1;
  }
  
  // 3. If dates are the same, sort by higher remaining area
  return b.remainingArea - a.remainingArea;
});
}, [jobs, searchTerm, farmerAcresMap,farmers]);
  const JobFormInline: React.FC<{ farmerId: string; existingPlots: any[] }> = ({ farmerId, existingPlots }) => (
    <div className="inline-job-form" onClick={e => e.stopPropagation()}>
      <div className="form-divider">Plot</div>
      <div className="radio-group">
        <label className="radio-label">
          <input type="radio" checked={plotMode === 'existing'} onChange={() => setPlotMode('existing')} />
          <span>Existing Plot</span>
        </label>
        <label className="radio-label">
          <input type="radio" checked={plotMode === 'new'} onChange={() => setPlotMode('new')} />
          <span>New Plot</span>
        </label>
      </div>

      {plotMode === 'existing' ? (
        <select className="form-select" value={selectedNewPlotId ?? ''} onChange={e => {
          const id = Number(e.target.value);
          const plot = existingPlots.find(p => p.id === id);
          setSelectedNewPlotId(id);
          if (plot) loadPlotActivityStatus(id, Number(plot.area_acres), farmerId);
        }}>
          <option value="">Select plot</option>
          {existingPlots.map(p => <option key={p.id} value={p.id}>{p.name} ({p.area_acres} ac)</option>)}
        </select>
      ) : (
        <div className="form-row">
          <input className="form-input" placeholder="Plot name" value={newPlot.name} onChange={e => setNewPlot({ ...newPlot, name: e.target.value })} />
          <input className="form-input" type="number" placeholder="Area (ac)" value={newPlot.area_acres || ''} onChange={e => {
            const v = parseFloat(e.target.value) || 0;
            setNewPlot({ ...newPlot, area_acres: v });
            if (newJob.base_date && v > 0) autoFillFromCalendar(v, newJob.base_date);
          }} />
        </div>
      )}

      {plotMode === 'new' && (
        <>
          <div className="form-row" style={{ marginTop: '0.5rem' }}>
            <input className="form-input" placeholder="Crop" value={newJob.crop_name} onChange={e => setNewJob({ ...newJob, crop_name: e.target.value })} />
            <input className="form-input" placeholder="Variety" value={newJob.variety} onChange={e => setNewJob({ ...newJob, variety: e.target.value })} />
          </div>
          <div className="form-group" style={{ marginTop: '0.5rem' }}>
            <label className="form-label">Base Date *</label>
            <input type="date" className="form-input" value={newJob.base_date} onChange={e => {
              setNewJob({ ...newJob, base_date: e.target.value });
              if (newPlot.area_acres > 0) autoFillFromCalendar(newPlot.area_acres, e.target.value);
            }} />
          </div>
          {autoFilledActivities.length > 0 && (
            <div className="activity-checklist" style={{ maxHeight: 200, overflowY: 'auto' }}>
              {autoFilledActivities.map((a, i) => (
                <div key={i} className="activity-check-row">
                  <label className="checkbox-label">
                    <input type="checkbox" checked={a.enabled} onChange={e => {
                      const u = [...autoFilledActivities]; u[i].enabled = e.target.checked;
                      setAutoFilledActivities(u); recalcAmount(u.filter(x => x.enabled));
                    }} />
                    <span>{a.activity_name}</span>
                  </label>
                  {a.enabled && (
                    <div className="form-row" style={{ marginTop: 4 }}>
                      <input type="number" className="form-input-sm" value={a.total_area} onChange={e => {
                        const u = [...autoFilledActivities]; u[i].total_area = parseFloat(e.target.value) || 0;
                        setAutoFilledActivities(u); recalcAmount(u.filter(x => x.enabled));
                      }} />
                      <input type="date" className="form-input-sm" value={a.scheduled_date} onChange={e => {
                        const u = [...autoFilledActivities]; u[i].scheduled_date = e.target.value;
                        setAutoFilledActivities(u);
                      }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {plotMode === 'existing' && selectedNewPlotId && notBookedActivities.length > 0 && (
        <div className="activity-checklist" style={{ maxHeight: 200, overflowY: 'auto', marginTop: '0.5rem' }}>
          {notBookedActivities.map((a, i) => (
            <div key={i} className="activity-check-row">
              <label className="checkbox-label">
                <input type="checkbox" checked={a.selected} onChange={e => {
                  const u = [...notBookedActivities]; u[i].selected = e.target.checked;
                  setNotBookedActivities(u); recalcFromNotBooked(u);
                }} />
                <span>{a.activity_name}</span>
              </label>
              {a.selected && (
                <div className="form-row" style={{ marginTop: 4 }}>
                  <input type="number" className="form-input-sm" value={a.total_area} onChange={e => {
                    const u = [...notBookedActivities]; u[i].total_area = parseFloat(e.target.value) || 0;
                    setNotBookedActivities(u); recalcFromNotBooked(u);
                  }} />
                  <input type="date" className="form-input-sm" value={a.scheduled_date} onChange={e => {
                    const u = [...notBookedActivities]; u[i].scheduled_date = e.target.value;
                    setNotBookedActivities(u);
                  }} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="inline-form-footer">
        <span style={{ fontSize: '0.82rem', color: '#475569' }}>₹{newJob.booking_amount.toFixed(0)} total</span>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn-secondary btn-sm" onClick={() => { setShowAddJob(null); resetJobForm(); }}>Cancel</button>
          <button className="btn-primary btn-sm" onClick={() => handleCreateJob(farmerId)}>Create Job</button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="jobs-panel">
      {/* Fixed top: Add New Farmer */}
      <div className="panel-top-actions">
        {/* <button className="btn-primary" style={{ width: '100%' }} onClick={() => { resetJobForm(); setIsNewFarmer(true); setShowNewFarmerModal(true); }}>
          <Plus size={15} /> Add New Farmer
        </button> */}
      </div>

      <div className="panel-header" style={{ paddingTop: '0.5rem' }}>
        <input type="text" className="form-input" placeholder="Search farmer..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
        {/* <button className="btn-secondary icon-only" onClick={onRefresh} disabled={loading} title="Refresh">🔄</button> */}
      </div>

      <div className="panel-content">
        {loading ? (
          <div className="empty-state"><div className="loading-spinner" /><p>Loading...</p></div>
        ) : farmerSummaries.length === 0 ? (
          <div className="empty-state"><div className="empty-state-icon">📋</div><p className="empty-state-text">No farmers found</p></div>
        ) : (
          <div className="jobs-list">

{farmerSummaries.map(s => {
  const isExpanded = expandedFarmerId === s.farmerId;
  const plots = farmerPlots[s.farmerId] || [];
  const isActive = s.remainingArea > 0;
  const todayStr = new Date().toISOString().split('T')[0];

  // Initials avatar
  const initials = (s.farmerName || '')
    .split(' ')
    .slice(0, 2)
    .map((n: string) => n[0])
    .join('')
    .toUpperCase();

  return (
    <div
      key={s.farmerId}
      className={`rounded-xl border transition-all duration-200 overflow-hidden ${
        isExpanded
          ? 'border-emerald-400 bg-emerald-50/50 shadow-sm shadow-emerald-100'
          : 'border-stone-200 bg-white hover:border-stone-300 hover:shadow-sm'
      }`}
      style={{ marginBottom: '8px' }}
    >
      {/* ── FARMER HEADER ── */}
      <button
        onClick={() => handleFarmerClick(s.farmerId, s.farmerName)}
        className="w-full text-left p-3 group"
        style={{ background: 'none', border: 'none', cursor: 'pointer', width: '100%' }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
          {/* Initials avatar */}
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.7rem', fontWeight: 700,
            background: isExpanded ? '#059669' : '#f5f5f4',
            color: isExpanded ? '#fff' : '#78716c',
            transition: 'all 0.15s',
            boxShadow: isExpanded ? '0 1px 4px rgba(5,150,105,0.25)' : 'none',
          }}>
            {initials}
          </div>

          {/* Name + meta */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontWeight: 600, fontSize: '0.875rem', color: '#1c1917', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1.2, margin: 0 }}>
              {s.farmerName}
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '3px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.72rem', color: '#a8a29e' }}>{s.plotCount} plot{s.plotCount !== 1 ? 's' : ''}</span>
              <span style={{ color: '#d4cdc9', fontSize: '0.65rem' }}>·</span>
              <span style={{ fontSize: '0.72rem', color: '#a8a29e' }}>
                {(farmerAcresMap?.[s.farmerId] ?? s.totalAcres ?? 0).toFixed(2)} ac
              </span>
              <span style={{ color: '#d4cdc9', fontSize: '0.65rem' }}>·</span>
              <span style={{ fontSize: '0.72rem', color: '#a8a29e' }}>{s.totalActivities} tasks</span>
            </div>
          </div>

          {/* Chevron */}
          <div style={{ flexShrink: 0, marginTop: '6px' }}>
            {isExpanded
              ? <ChevronUp size={14} style={{ color: '#10b981' }} />
              : <ChevronDown size={14} style={{ color: '#d4cdc9' }} />
            }
          </div>
        </div>

        {/* Phone + Next + Call button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '8px', marginLeft: '46px', flexWrap: 'wrap' }}>
          {s.mobileNumber && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Phone size={10} style={{ color: '#d4cdc9' }} />
              <span style={{ fontSize: '0.72rem', color: '#a8a29e', fontVariantNumeric: 'tabular-nums' }}>{s.mobileNumber}</span>
            </div>
          )}
          {s.nearestDate && (
            <span style={{ fontSize: '0.72rem', color: '#a8a29e', whiteSpace: 'nowrap' }}>
              Next: {new Date(s.nearestDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
            </span>
          )}
          {s.poc && (
            <span style={{ fontSize: '0.68rem', color: '#a8a29e' }}>🧑‍💼 {s.poc}</span>
          )}
          {s.mobileNumber && (
            <button
              type="button"
              onClick={e => {
                e.stopPropagation();
                setDialpadNumber(s.mobileNumber || '');
                setDialpadOpen(true);
              }}
              style={{
                marginLeft: 'auto',
                display: 'inline-flex', alignItems: 'center', gap: '4px',
                fontSize: '0.72rem', fontWeight: 600,
                padding: '4px 10px', borderRadius: '8px',
                background: '#059669', color: '#fff', border: 'none',
                cursor: 'pointer', boxShadow: '0 1px 3px rgba(5,150,105,0.3)',
              }}
            >
              <Phone size={10} /> Call
            </button>
          )}
        </div>
      </button>

      {/* ── EXPANDED: PLOTS ── */}
      {isExpanded && (
        <div style={{ padding: '0 12px 12px', borderTop: '1px solid rgba(167,243,208,0.4)' }}>
          <div style={{ paddingTop: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {plots.length === 0 ? (
              <p style={{ fontSize: '0.83rem', color: '#a8a29e', padding: '6px 0' }}>No plots yet</p>
            ) : (() => {
              const sortedPlots = [...plots].sort((a: any, b: any) => {
                const getMeta = (plotObj: any) => {
                  const pJobs = s.jobs.filter((j: any) => Number(j.plot) === Number(plotObj.id));
                  let nearest: string | null = null;
                  let rem = 0;
                  pJobs.forEach((j: any) => (j.activities || []).forEach((act: any) => {
                    if (act.scheduled_date && act.scheduled_date >= todayStr) {
                      if (!nearest || act.scheduled_date < nearest) nearest = act.scheduled_date;
                    }
                    if (act.allocated_area < act.total_area && (act.scheduled_date <= (nearest || todayStr))) {
                      rem += (Number(act.total_area) - Number(act.allocated_area));
                    }
                  }));
                  return { nearest, rem };
                };
                const dA = getMeta(a), dB = getMeta(b);
                if (dA.nearest !== dB.nearest) {
                  if (!dA.nearest) return 1; if (!dB.nearest) return -1;
                  return dA.nearest < dB.nearest ? -1 : 1;
                }
                return dB.rem - dA.rem;
              });

              return sortedPlots.map((plot: any) => {
                const isPlotExpanded = expandedPlotId === plot.id;
                const currentPlotJobs = isPlotExpanded
                  ? (plotJobs[plot.id] || s.jobs.filter((j: any) =>
                      Number(j.plot) === Number(plot.id) ||
                      (j.activities || []).some((a: any) => Number(a.plot) === Number(plot.id))
                    ))
                  : s.jobs.filter((j: any) => Number(j.plot) === Number(plot.id));

                let plotNearestDate: string | null = null;
                currentPlotJobs.forEach((j: any) => (j.activities || []).forEach((a: any) => {
                  if (a.scheduled_date >= todayStr) {
                    if (!plotNearestDate || a.scheduled_date < plotNearestDate) plotNearestDate = a.scheduled_date;
                  }
                }));

                const plotRemaining = currentPlotJobs.reduce((acc: number, job: any) =>
                  acc + (job.activities || []).reduce((aAcc: number, act: any) => {
                    const isUnallocated = Number(act.allocated_area) < Number(act.total_area);
                    if (isUnallocated && (act.scheduled_date < todayStr || act.scheduled_date === plotNearestDate))
                      return aAcc + (Number(act.total_area) - Number(act.allocated_area));
                    return aAcc;
                  }, 0), 0
                );

                return (
                  <div key={plot.id} style={{ background: '#fff', borderRadius: '10px', border: '1px solid #e7e5e4', overflow: 'hidden', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}>
                    {/* Plot header */}
                    <button
                      onClick={() => handlePlotClick(plot.id, plot.area_acres, s.farmerId)}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px', background: 'none', border: 'none', cursor: 'pointer' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
                        {/* MapPin icon box */}
                        <div style={{ width: '26px', height: '26px', borderRadius: '7px', background: '#fef2f2', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          <MapPin size={13} style={{ color: '#f87171' }} />
                        </div>
                        <div style={{ textAlign: 'left' }}>
                          <p style={{ fontSize: '0.82rem', fontWeight: 700, color: '#44403c', margin: 0, lineHeight: 1.2 }}>
                            {plot.name}
                          </p>
                          {plot.crop_name && (
                            <p style={{ fontSize: '0.68rem', color: '#a8a29e', margin: '1px 0 0' }}>
                              {plot.crop_name}{plot.variety ? ` · ${plot.variety}` : ''}
                            </p>
                          )}
                          {plotRemaining > 0 && (
                            <div style={{ marginTop: '2px' }}>
                              <span style={{ fontSize: '0.7rem', color: '#2563eb', fontWeight: 700 }}>
                                {plotRemaining.toFixed(2)} ac remaining
                              </span>
                              {plotNearestDate && (
                                <span style={{ fontSize: '0.65rem', color: '#3b82f6', marginLeft: '6px' }}>
                                  Next: {new Date(plotNearestDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                        <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#059669', background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '2px 8px', borderRadius: '6px' }}>
                          {plot.area_acres} ac
                        </span>
                        {isPlotExpanded
                          ? <ChevronUp size={12} style={{ color: '#a8a29e' }} />
                          : <ChevronDown size={12} style={{ color: '#d4cdc9' }} />
                        }
                      </div>
                    </button>

                    {/* Plot tasks */}
                    {isPlotExpanded && (
                      <div style={{ borderTop: '1px solid #f5f5f4' }}>
                        {currentPlotJobs.length === 0 ? (
                          <p style={{ fontSize: '0.83rem', color: '#a8a29e', padding: '10px' }}>No jobs</p>
                        ) : currentPlotJobs.map((job: any) => (
                          <div key={job.job_id}>
                            {/* Crop header */}
                            <div style={{ padding: '6px 12px 2px', background: '#fafaf9' }}>
                              <span style={{ fontSize: '0.75rem', color: '#78716c', fontWeight: 600 }}>
                                {job.crop_name}{job.variety ? ` · ${job.variety}` : ''}
                              </span>
                            </div>

                            {/* Activities */}
                            {[...(job.activities || [])].sort((a: any, b: any) => {
                              const isAB = a.scheduled_date < todayStr && a.allocated_area < a.total_area;
                              const isBB = b.scheduled_date < todayStr && b.allocated_area < b.total_area;
                              const isAN = a.scheduled_date === plotNearestDate;
                              const isBN = b.scheduled_date === plotNearestDate;
                              if (isAB && !isBB) return -1; if (!isAB && isBB) return 1;
                              if (isAN && !isBN) return -1; if (!isAN && isBN) return 1;
                              return (a.scheduled_date || '').localeCompare(b.scheduled_date || '');
                            }).map((act: any, ti: number, arr: any[]) => {
                              const isNextJob = act.scheduled_date === plotNearestDate;
                              const isBacklog = act.scheduled_date < todayStr && act.allocated_area < act.total_area;
                              return (
                                <div
                                  key={act.id}
                                  style={{
                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                    padding: '9px 12px',
                                    borderTop: ti > 0 ? '1px solid #f5f5f4' : 'none',
                                    background: isNextJob ? '#f0fdf4' : isBacklog ? '#fef2f2' : '#fff',
                                    transition: 'background 0.1s',
                                  }}
                                >
                                  <div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                                      <span style={{ fontSize: '0.78rem', color: '#44403c', fontWeight: isNextJob ? 700 : 500 }}>
                                        {act.activity_name}
                                      </span>
                                      {isNextJob && (
                                        <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: '#059669', color: '#fff', letterSpacing: '0.04em' }}>
                                          NEXT
                                        </span>
                                      )}
                                      {isBacklog && (
                                        <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: '#fee2e2', color: '#dc2626', letterSpacing: '0.04em' }}>
                                          BACKLOG
                                        </span>
                                      )}
                                    </div>
                                    <span style={{ fontSize: '0.7rem', color: '#a8a29e' }}>{act.total_area} ac</span>
                                  </div>
                                  {act.scheduled_date && (
                                    <span style={{
                                      fontSize: '0.7rem', color: isNextJob ? '#059669' : isBacklog ? '#ef4444' : '#a8a29e',
                                      fontWeight: isNextJob || isBacklog ? 600 : 400,
                                      background: '#f5f5f4', padding: '2px 7px', borderRadius: '5px',
                                      fontVariantNumeric: 'tabular-nums', flexShrink: 0, marginLeft: '8px',
                                    }}>
                                      {new Date(act.scheduled_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                                    </span>
                                  )}
                                </div>
                              );
                            })}

                            {/* Next job footer */}
                            {plotNearestDate && (
                              <div style={{ padding: '6px 12px', background: '#f5f5f4', borderTop: '1px solid #e7e5e4', fontSize: '0.7rem', color: '#78716c', fontWeight: 500 }}>
                                Next job: {new Date(plotNearestDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              });
            })()}
          </div>
        </div>
      )}
    </div>
  );
})}
          </div>
        )}
      </div>
<Dialpad
  isOpen={dialpadOpen}
  number={dialpadNumber}
  onClose={() => setDialpadOpen(false)}
  onNumberChange={setDialpadNumber}
/>

      {/* Edit Activity Modal */}
      {editingActivity && (
        <div className="modal-overlay" onClick={() => setEditingActivity(null)}>
          <div className="modal-content modal-sm" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Edit Activity</h3>
              <button onClick={() => setEditingActivity(null)} className="modal-close"><X size={20} /></button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Activity</label>
                <input className="form-input" value={editingActivity.activity_name} disabled />
              </div>
              <div className="form-group">
                <label className="form-label">Total Area (ac)</label>
                <input type="number" step="0.01" className="form-input" value={editingActivity.total_area}
                  onChange={e => setEditingActivity({ ...editingActivity, total_area: parseFloat(e.target.value) || 0 })} />
                {editingActivity.total_area < editingActivity.allocated_area && (
                  <small style={{ color: '#dc2626' }}>⚠️ Cannot be less than allocated ({editingActivity.allocated_area} ac)</small>
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Rate (₹/ac)</label>
                <input type="number" step="0.01" className="form-input" value={editingActivity.rate_per_acre}
                  onChange={e => setEditingActivity({ ...editingActivity, rate_per_acre: parseFloat(e.target.value) || 0 })} />
              </div>
              <div className="form-group">
                <label className="form-label">Scheduled Date</label>
                <input type="date" className="form-input" value={editingActivity.scheduled_date || ''}
                  onChange={e => setEditingActivity({ ...editingActivity, scheduled_date: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="checkbox-label">
                  <input type="checkbox" checked={editingActivity.is_strict}
                    onChange={e => setEditingActivity({ ...editingActivity, is_strict: e.target.checked })} />
                  <span>Strict</span>
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setEditingActivity(null)}>Cancel</button>
              <button className="btn-primary" onClick={handleEditActivity}
                disabled={editingActivity.total_area < editingActivity.allocated_area}>Save</button>
            </div>
          </div>
        </div>
      )}

      {/* New Farmer Modal */}
      {showNewFarmerModal && (
        <div className="modal-overlay" onClick={() => setShowNewFarmerModal(false)}>
          <div className="modal-content modal-xl" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Add New Farmer + Job</h3>
              <button onClick={() => setShowNewFarmerModal(false)} className="modal-close"><X size={20} /></button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Farmer Name *</label>
                <input className="form-input" value={newJob.farmer_name} onChange={e => setNewJob({ ...newJob, farmer_name: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Mobile</label>
                <input type="tel" inputMode="numeric" maxLength={10} className="form-input" placeholder="9876543210"
                  value={newJob.mobile_number} onChange={e => { const v = e.target.value.replace(/\D/g, '').slice(0, 10); setNewJob({ ...newJob, mobile_number: v }); }} />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Crop</label>
                  <input className="form-input" value={newJob.crop_name} onChange={e => setNewJob({ ...newJob, crop_name: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">Variety</label>
                  <input className="form-input" value={newJob.variety} onChange={e => setNewJob({ ...newJob, variety: e.target.value })} />
                </div>
              </div>
              <div className="form-divider">New Plot</div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Plot Name</label>
                  <input className="form-input" placeholder="Plot 1" value={newPlot.name} onChange={e => setNewPlot({ ...newPlot, name: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">Area (ac) *</label>
                  <input type="number" step="0.01" className="form-input" value={newPlot.area_acres || ''}
                    onChange={e => {
                      const v = parseFloat(e.target.value) || 0;
                      setNewPlot({ ...newPlot, area_acres: v });
                      if (newJob.base_date && v > 0) autoFillFromCalendar(v, newJob.base_date);
                    }} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Base Date *</label>
                <input type="date" className="form-input" value={newJob.base_date}
                  onChange={e => { setNewJob({ ...newJob, base_date: e.target.value }); if (newPlot.area_acres > 0) autoFillFromCalendar(newPlot.area_acres, e.target.value); }} />
              </div>
              {autoFilledActivities.length > 0 && (
                <>
                  <div className="form-divider">Activities</div>
                  <div className="activity-checklist">
                    {autoFilledActivities.map((a, i) => (
                      <div key={i} className={`activity-check-row ${!a.enabled ? 'disabled' : ''}`}>
                        <label className="checkbox-label">
                          <input type="checkbox" checked={a.enabled} onChange={e => {
                            const u = [...autoFilledActivities]; u[i].enabled = e.target.checked;
                            setAutoFilledActivities(u); recalcAmount(u.filter(x => x.enabled));
                          }} />
                          <span>{a.activity_name}</span>
                        </label>
                        {a.enabled && (
                          <div className="activity-check-details">
                            <div className="form-group-inline"><label>Area</label>
                              <input type="number" step="0.01" className="form-input-sm" value={a.total_area} onChange={e => {
                                const u = [...autoFilledActivities]; u[i].total_area = parseFloat(e.target.value) || 0;
                                setAutoFilledActivities(u); recalcAmount(u.filter(x => x.enabled));
                              }} />
                            </div>
                            <div className="form-group-inline"><label>Rate</label>
                              <input type="number" step="0.01" className="form-input-sm" value={a.rate_per_acre} onChange={e => {
                                const u = [...autoFilledActivities]; u[i].rate_per_acre = parseFloat(e.target.value) || 0;
                                setAutoFilledActivities(u); recalcAmount(u.filter(x => x.enabled));
                              }} />
                            </div>
                            <div className="form-group-inline"><label>Date</label>
                              <input type="date" className="form-input-sm" value={a.scheduled_date} onChange={e => {
                                const u = [...autoFilledActivities]; u[i].scheduled_date = e.target.value;
                                setAutoFilledActivities(u);
                              }} />
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="booking-summary">
                    <div className="summary-row">
                      <span className="summary-label">Total:</span>
                      <span className="summary-value">₹{newJob.booking_amount.toFixed(2)}</span>
                    </div>
                    <div className="summary-row">
                      <span className="summary-label">Payment:</span>
                      <select className="form-select-sm" value={newJob.payment_status} onChange={e => setNewJob({ ...newJob, payment_status: e.target.value })}>
                        <option value="pending">Pending</option>
                        <option value="partial">Partial</option>
                        <option value="paid">Paid</option>
                      </select>
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowNewFarmerModal(false)}>Cancel</button>
              <button className="btn-primary" onClick={() => handleCreateJob()} disabled={!newJob.farmer_name || !newPlot.area_acres || !newJob.base_date}>
                Create Farmer + Job
              </button>
            </div>
          </div>
        </div>
      )}
      
    </div>
  );
};

export default JobsPanel;