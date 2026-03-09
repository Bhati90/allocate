// App.tsx (TenderFront)
import React, { useEffect, useState, useRef,useCallback } from 'react';
import ReactDOM from 'react-dom';
import FarmScheduler from './Farm';
import ClusterActivityCalendar from './ClusterCalender';
import { API_BASE_URL } from './types/config';
import { useNavigate } from 'react-router-dom';

import {X, Save,Edit2 ,Calendar,User,Users} from 'lucide-react'
// import './Farm.css';
import toast from 'react-hot-toast';
interface Cluster {
  date_range?: {
    start_date: string | null;
    end_date: string | null;
  };
  allocation_count :number;
  activity_count : number;
  id: number;
  farmer_count: number;
  mukkadam_count: number;
  name: string;
  district?: string;
  taluka?: string;
  village?: string;
  districts?: string[];
  talukas?: string[];
  villages?: string[];
  farmer_due: number;    // ← new
  mukkadam_due: number;
}

interface StateOption {
  state_code: string;
  state_name_english: string;
  state_name_local: string;
}

interface DistrictOption {
  districtcode: string;
  districtnameenglish: string;
  districtlocalname: string;
}

interface TalukaOption {
  subdistrictcode: string;
  subdistrictnameenglish: string;
  subdistrictlocalname: string;
  districtcode?: string;
}

interface VillageOption {
  villagecode: string;
  villagenameenglish: string;
  villagelocalname: string;
  subdistrictcode?: string;
  districtcode?: string;
}

interface SelectedLocation {
  village: VillageOption;
  talukaName: string;
  districtName: string;
  talukaCode: string;
  districtCode: string;
}

// ─── LocationSearch ───────────────────────────────────────────────────────────
interface LocationSearchProps {
  stateCode: string;
  onSelectionChange: (locations: SelectedLocation[]) => void;
}

const LocationSearch: React.FC<LocationSearchProps> = ({ stateCode, onSelectionChange }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<VillageOption[]>([]);
  const [selected, setSelected] = useState<SelectedLocation[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // Use refs for lookup maps — avoids stale closure issues entirely
  const talukaMapRef = useRef<Map<string, TalukaOption>>(new Map());
  const districtMapRef = useRef<Map<string, DistrictOption>>(new Map());

  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load districts + talukas into ref maps once per stateCode
  useEffect(() => {
    talukaMapRef.current = new Map();
    districtMapRef.current = new Map();

    if (!stateCode) return;

    const load = async () => {
      try {
        const distRes = await fetch(`${API_BASE_URL}/locations/districts/?state_code=${stateCode}`);
        const distData: DistrictOption[] = await distRes.json();
        distData.forEach(d => districtMapRef.current.set(String(d.districtcode), d));

        const talukaPromises = distData.map(d =>
          fetch(`${API_BASE_URL}/locations/talukas/?state_code=${stateCode}&district_code=${d.districtcode}`)
            .then(r => r.json()).catch(() => [])
        );
        const arrays = await Promise.all(talukaPromises);
        arrays.flat().forEach((t: TalukaOption) => {
          talukaMapRef.current.set(String(t.subdistrictcode), t);
        });
      } catch (e) {
        console.error('Failed to load meta', e);
      }
    };

    load();
  }, [stateCode]);

  // Search villages via API on each keystroke
  useEffect(() => {
    if (!query || query.length < 1) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `${API_BASE_URL}/locations/search_villages/?state_code=${stateCode}&q=${encodeURIComponent(query)}`
        );
        const data: VillageOption[] = await res.json();
        setResults(data);
        setIsOpen(data.length > 0);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query, stateCode]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleSelect = (village: VillageOption) => {
    if (selected.some(s => s.village.villagecode === village.villagecode)) return;

    const talukaCode = String(village.subdistrictcode || '');
    const taluka = talukaMapRef.current.get(talukaCode);
    const districtCode = taluka
      ? String(taluka.districtcode || '')
      : String(village.districtcode || '');
    const district = districtMapRef.current.get(districtCode);

    const loc: SelectedLocation = {
      village,
      talukaCode,
      districtCode,
      talukaName: taluka?.subdistrictnameenglish || talukaCode,
      districtName: district?.districtnameenglish || districtCode,
    };

    const updated = [...selected, loc];
    setSelected(updated);
    onSelectionChange(updated);
    setQuery('');
    setResults([]);
    setIsOpen(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleRemove = (villagecode: string) => {
    const updated = selected.filter(s => s.village.villagecode !== villagecode);
    setSelected(updated);
    onSelectionChange(updated);
  };

  const highlightMatch = (text: string) => {
    if (!query || !text) return <span>{text}</span>;
    const idx = text.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return <span>{text}</span>;
    return (
      <span>
        {text.slice(0, idx)}
        <strong style={{ color: '#1d4ed8', fontWeight: 700 }}>
          {text.slice(idx, idx + query.length)}
        </strong>
        {text.slice(idx + query.length)}
      </span>
    );
  };

  return (
    <div style={{ position: 'relative', marginTop: '0.25rem' }}>

      {/* Tag input box */}
      <div
        style={{
          display: 'flex', flexWrap: 'wrap', alignItems: 'center',
          gap: '0.35rem', border: '1.5px solid #d1d5db', borderRadius: '8px',
          padding: '0.4rem 0.75rem', background: '#fff', minHeight: '44px', cursor: 'text',
        }}
        onClick={() => inputRef.current?.focus()}
      >
        {selected.map(loc => (
          <span
            key={loc.village.villagecode}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '4px',
              background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '6px',
              padding: '2px 8px', fontSize: '0.82rem', color: '#1e40af',
              fontWeight: 500, whiteSpace: 'nowrap',
            }}
          >
            {loc.village.villagenameenglish}
            {loc.talukaName && (
              <span style={{ color: '#93c5fd', fontSize: '0.75rem' }}>
                · {loc.talukaName}
              </span>
            )}
            <button
              type="button"
              onMouseDown={e => {
                e.preventDefault();
                e.stopPropagation();
                handleRemove(loc.village.villagecode);
              }}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: '#60a5fa', padding: '0 2px', fontSize: '14px',
                lineHeight: 1, display: 'flex', alignItems: 'center',
              }}
            >×</button>
          </span>
        ))}

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          placeholder={selected.length === 0 ? 'Type village name to search...' : 'Add more...'}
          style={{
            border: 'none', outline: 'none', flex: 1,
            minWidth: '140px', fontSize: '0.9rem',
            background: 'transparent', color: '#111827',
          }}
        />
        {loading && (
          <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>searching...</span>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && results.length > 0 && (
        <div
          ref={dropdownRef}
          style={{
            position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 9999,
            background: '#fff', border: '1.5px solid #e5e7eb', borderRadius: '8px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.15)', maxHeight: '280px',
            overflowY: 'auto', marginTop: '4px',
          }}
        >
          {results.map((v, idx) => {
            const talukaCode = String(v.subdistrictcode || '');
            const taluka = talukaMapRef.current.get(talukaCode);
            const districtCode = taluka ? String(taluka.districtcode || '') : String(v.districtcode || '');
            const district = districtMapRef.current.get(districtCode);
            const isAlreadySelected = selected.some(s => s.village.villagecode === v.villagecode);

            return (
              <div
                key={v.villagecode}
                onMouseDown={e => {
                  e.preventDefault(); // critical — prevents blur before select fires
                  if (!isAlreadySelected) handleSelect(v);
                }}
                style={{
                  padding: '0.6rem 1rem',
                  cursor: isAlreadySelected ? 'not-allowed' : 'pointer',
                  background: isAlreadySelected ? '#f9fafb' : idx % 2 === 0 ? '#fff' : '#fafafa',
                  opacity: isAlreadySelected ? 0.5 : 1,
                  borderBottom: idx < results.length - 1 ? '1px solid #f3f4f6' : 'none',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}
                onMouseEnter={e => {
                  if (!isAlreadySelected)
                    (e.currentTarget as HTMLDivElement).style.background = '#eff6ff';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLDivElement).style.background =
                    isAlreadySelected ? '#f9fafb' : idx % 2 === 0 ? '#fff' : '#fafafa';
                }}
              >
                <div>
                  <div style={{ fontSize: '0.9rem', color: '#111827', fontWeight: 500 }}>
                    {highlightMatch(v.villagenameenglish)}
                  </div>
                  {v.villagelocalname && v.villagelocalname !== v.villagenameenglish && (
                    <div style={{ fontSize: '0.78rem', color: '#6b7280' }}>{v.villagelocalname}</div>
                  )}
                </div>
                <div style={{ textAlign: 'right', fontSize: '0.78rem', color: '#9ca3af' }}>
                  {taluka && <div>{taluka.subdistrictnameenglish}</div>}
                  {district && <div>{district.districtnameenglish}</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Selected list below input */}
      {selected.length > 0 && (
        <div style={{ marginTop: '0.6rem' }}>
          <div style={{
            fontSize: '0.72rem', color: '#6b7280', marginBottom: '0.35rem',
            fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>
            {selected.length} village{selected.length > 1 ? 's' : ''} selected
          </div>
          {selected.map(loc => (
            <div
              key={loc.village.villagecode}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '0.35rem 0.75rem', background: '#f0f9ff',
                borderRadius: '6px', fontSize: '0.83rem', marginBottom: '0.3rem',
              }}
            >
              <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600, color: '#1e40af' }}>
                  {loc.village.villagenameenglish}
                </span>
                {loc.talukaName && (
                  <>
                    <span style={{ color: '#94a3b8' }}>›</span>
                    <span style={{ color: '#475569' }}>{loc.talukaName}</span>
                  </>
                )}
                {loc.districtName && (
                  <>
                    <span style={{ color: '#94a3b8' }}>›</span>
                    <span style={{ color: '#64748b' }}>{loc.districtName}</span>
                  </>
                )}
              </div>
              <button
                type="button"
                onClick={() => handleRemove(loc.village.villagecode)}
                style={{
                  background: 'none', border: 'none', color: '#ef4444',
                  cursor: 'pointer', fontSize: '0.8rem', padding: '0 4px',
                }}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};


// ─── Types ───────────────────────────────────────────────
interface PlotInfo {
  plot_id: number;
  plot_code: string;
  name: string;
  area_acres: number;
  crop_name: string;
  in_this_cluster: boolean;
  other_clusters: { id: number; name: string }[];
}
interface FarmerResult {
  farmer_id: string;
  farmer_name: string;
  phone_number: string;
  location: string;
  in_this_cluster: boolean;
  other_clusters: { id: number; name: string }[];
  plots: PlotInfo[];
}
interface MukkadamResult {
  id: number;
  name: string;
  mobile: string;
  crew_size: number;
  max_crew_capacity: number;
  village: string;
  district: string;
  activities: { name: string; price: string }[];
  in_this_cluster: boolean;
  other_clusters: { id: number; name: string }[];
}

// ─── AddToClusterModal ────────────────────────────────────
interface AddToClusterModalProps {
  clusterId: number;
  clusterName: string;
  mode: 'farmer' | 'mukkadam';
  onClose: () => void;
}
// ─── EditClusterModal ─────────────────────────────────────────────────────────
interface EditClusterModalProps {
  cluster: Cluster;
  onClose: () => void;
  onSaved: (updated: Cluster) => void;
}

const EditClusterModal: React.FC<EditClusterModalProps> = ({ cluster, onClose, onSaved }) => {
  const [name, setName]                       = useState(cluster.name);
  const [selectedState, setSelectedState]     = useState<string>('MH');
  const [selectedLocations, setSelectedLocations] = useState<SelectedLocation[]>([]);
  const [saving, setSaving]                   = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const body: any = { name };

      if (selectedLocations.length > 0) {
        body.district_codes = [...new Set(selectedLocations.map(l => l.districtCode).filter(Boolean))];
        body.taluka_codes   = [...new Set(selectedLocations.map(l => l.talukaCode).filter(Boolean))];
        body.village_codes  = selectedLocations.map(l => l.village.villagecode);
        body.districts      = [...new Set(selectedLocations.map(l => l.districtName).filter(Boolean))];
        body.talukas        = [...new Set(selectedLocations.map(l => l.talukaName).filter(Boolean))];
        body.villages       = selectedLocations.map(l => l.village.villagenameenglish);
      }

      const token = localStorage.getItem('auth_token');

    const res = await fetch(`${API_BASE_URL}/api/clusters/${cluster.id}/update_locations/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Token ${token}` } : {}),
      },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      toast.success('Cluster updated!');
      onSaved(data);
      onClose();
    } catch (e) {
      toast.error('Failed to update cluster');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}
        style={{ maxWidth: '520px', width: '100%', borderRadius: '16px', padding: '24px' }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h3 style={{ fontWeight: 700, fontSize: '1.1rem', color: '#111827' }}>
            ✏️ Edit Cluster
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        {/* Name */}
        <label className="form-label">
          Cluster name
          <input
            className="form-input"
            value={name}
            onChange={e => setName(e.target.value)}
          />
        </label>

        {/* Current villages info */}
        {cluster.villages && cluster.villages.length > 0 && (
          <div style={{
            marginTop: '12px', padding: '10px 14px',
            background: '#f0f9ff', borderRadius: '10px',
            fontSize: '0.8rem', color: '#1e40af',
          }}>
            <strong>Current villages:</strong>{' '}
            {Array.isArray(cluster.villages)
              ? cluster.villages.join(', ')
              : cluster.villages}
          </div>
        )}

        {/* New villages — optional, only updates if selections made */}
        <label className="form-label" style={{ marginTop: '16px', display: 'block' }}>
          Replace villages (optional)
          <p style={{ fontSize: '0.75rem', color: '#9ca3af', margin: '2px 0 6px' }}>
            Leave empty to keep existing villages. Select new ones to replace all.
          </p>
          <select
            className="form-input"
            value={selectedState}
            onChange={e => {
              setSelectedState(e.target.value);
              setSelectedLocations([]);
            }}
            style={{ marginBottom: '8px' }}
          >
            <option value="MH">Maharashtra</option>
            <option value="KA">Karnataka</option>
            <option value="UP">Uttar Pradesh</option>
          </select>
          <LocationSearch
            key={selectedState}
            stateCode={selectedState}
            onSelectionChange={setSelectedLocations}
          />
        </label>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '10px', marginTop: '24px' }}>
          <button
            onClick={onClose}
            style={{
              flex: 1, padding: '10px', borderRadius: '10px',
              border: '1px solid #e5e7eb', background: '#fff',
              color: '#374151', fontWeight: 600, cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !name}
            style={{
              flex: 1, padding: '10px', borderRadius: '10px',
              background: saving ? '#93c5fd' : '#2563eb',
              color: '#fff', fontWeight: 700, cursor: 'pointer', border: 'none',
            }}
          >
            {saving ? 'Saving...' : '💾 Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};

export const AddToClusterModal: React.FC<AddToClusterModalProps> = ({
  clusterId, clusterName, mode, onClose
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<FarmerResult[] | MukkadamResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
const [selectedMukkadamForEfficiency, setSelectedMukkadamForEfficiency] = useState<MukkadamResult | null>(null);
const [editableActivities, setEditableActivities] = useState<any[]>([]);

const handleInitiateEfficiencyEdit = (m: MukkadamResult) => {
  console.log('activities:', m.activities); // ← check what fields exist
  setSelectedMukkadamForEfficiency(m);
  setEditableActivities(m.activities.map((a: any) => ({
    rate_id: a.id,
    name: a.name,
    productivity: a.productivity || 0.15
  })));
};

const handleSaveSingleEfficiency = async (rateId: number, index: number) => {
  const newProductivity = editableActivities[index].productivity;
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/mukkadam-rates/${rateId}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ productivity_per_worker: newProductivity })
    });

    if (response.ok) {
      toast.success('Efficiency saved to Mukkadam profile');
    } else {
      toast.error('Failed to update efficiency');
    }
  } catch (error) {
    console.error('Error updating efficiency:', error);
  }
};
  // Farmer state
  const [expandedFarmer, setExpandedFarmer] = useState<string | null>(null);
  const [selectedPlots, setSelectedPlots] = useState<Record<string, Set<number>>>({});

  // Confirm state
  const [confirmPending, setConfirmPending] = useState<{
    type: 'farmer' | 'mukkadam';
    id: string | number;
    name: string;
    otherClusters: { id: number; name: string }[];
    plotIds?: number[];
  } | null>(null);

  // Search
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (query.length < 1) { setResults([]); return; }
      setLoading(true);
      try {
        const endpoint = mode === 'farmer'
          ? `${API_BASE_URL}/api/cluster/${clusterId}/search_farmers/?q=${encodeURIComponent(query)}`
          : `${API_BASE_URL}/api/cluster/${clusterId}/search_mukkadams/?q=${encodeURIComponent(query)}`;
        const res = await fetch(endpoint);
        setResults(await res.json());
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query, clusterId, mode]);

  const togglePlot = (farmerId: string, plotId: number) => {
    setSelectedPlots(prev => {
      const next = { ...prev };
      if (!next[farmerId]) next[farmerId] = new Set();
      else next[farmerId] = new Set(next[farmerId]);
      if (next[farmerId].has(plotId)) next[farmerId].delete(plotId);
      else next[farmerId].add(plotId);
      return next;
    });
  };

  const handleAddFarmer = (farmer: FarmerResult) => {
    const plots = Array.from(selectedPlots[farmer.farmer_id] || new Set<number>());
    if (farmer.other_clusters.length > 0) {
      setConfirmPending({
        type: 'farmer', id: farmer.farmer_id, name: farmer.farmer_name,
        otherClusters: farmer.other_clusters, plotIds: plots,
      });
    } else {
      doAddFarmer(farmer.farmer_id, plots);
    }
  };

  const handleAddMukkadam = (m: MukkadamResult) => {
    if (m.other_clusters.length > 0) {
      setConfirmPending({
        type: 'mukkadam', id: m.id, name: m.name,
        otherClusters: m.other_clusters,
      });
    } else {
      doAddMukkadam(m.id);
    }
  };

  const doAddFarmer = async (farmerId: string, plotIds: number[]) => {
    setSaving(true);
    try {
      await fetch(`${API_BASE_URL}/api/cluster/${clusterId}/add_farmer/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ farmer_id: farmerId, plot_ids: plotIds }),
      });
      // Refresh results
      const res = await fetch(
        `${API_BASE_URL}/api/cluster/${clusterId}/search_farmers/?q=${encodeURIComponent(query)}`
      );
      setResults(await res.json());
      setConfirmPending(null);
    } finally {
      setSaving(false);
    }
  };

  const doAddMukkadam = async (mukkadamId: number) => {
    setSaving(true);
    try {
      await fetch(`${API_BASE_URL}/api/cluster/${clusterId}/add_mukkadam/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mukkadam_id: mukkadamId }),
      });
      const res = await fetch(
        `${API_BASE_URL}/api/cluster/${clusterId}/search_mukkadams/?q=${encodeURIComponent(query)}`
      );
      setResults(await res.json());
      setConfirmPending(null);
    } finally {
      setSaving(false);
    }
  };

  const isFarmerMode = mode === 'farmer';

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      zIndex: 10000, display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: '#fff', borderRadius: '14px', width: '560px',
        maxHeight: '85vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 24px 60px rgba(0,0,0,0.25)',
      }}>
        {/* Header */}
        <div style={{
          padding: '1.2rem 1.5rem', borderBottom: '1px solid #e5e7eb',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.05rem', color: '#111827' }}>
              Add {isFarmerMode ? 'Farmer' : 'Mukkadam'} to Cluster
            </div>
            <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '2px' }}>
              Cluster: <strong>{clusterName}</strong>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: '1.4rem', color: '#9ca3af', lineHeight: 1,
          }}>×</button>
        </div>

        {/* Search */}
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid #f3f4f6' }}>
          <input
            autoFocus
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={`Search ${isFarmerMode ? 'farmer name or phone' : 'mukkadam name or mobile'}...`}
            style={{
              width: '100%', padding: '0.6rem 1rem', border: '1.5px solid #d1d5db',
              borderRadius: '8px', fontSize: '0.9rem', outline: 'none',
              boxSizing: 'border-box',
            }}
          />
        </div>

        {/* Results */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem 1.5rem' }}>
          {loading && (
            <div style={{ textAlign: 'center', color: '#9ca3af', padding: '2rem' }}>
              Searching...
            </div>
          )}

          {!loading && results.length === 0 && query.length > 0 && (
            <div style={{ textAlign: 'center', color: '#9ca3af', padding: '2rem' }}>
              No results found
            </div>
          )}

          {!loading && query.length === 0 && (
            <div style={{ textAlign: 'center', color: '#d1d5db', padding: '2rem', fontSize: '0.85rem' }}>
              Type to search
            </div>
          )}

          {/* FARMER RESULTS */}
          {isFarmerMode && (results as FarmerResult[]).map(farmer => (
            <div key={farmer.farmer_id} style={{
              border: '1.5px solid #e5e7eb', borderRadius: '10px',
              marginBottom: '0.75rem', overflow: 'hidden',
            }}>
              {/* Farmer row */}
              <div style={{
                padding: '0.75rem 1rem', background: farmer.in_this_cluster ? '#f0fdf4' : '#fff',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 700, color: '#111827' }}>{farmer.farmer_name}</span>
                    {farmer.in_this_cluster && (
                      <span style={{
                        background: '#dcfce7', color: '#15803d',
                        fontSize: '0.7rem', fontWeight: 700,
                        padding: '1px 7px', borderRadius: '999px',
                      }}>✓ In this cluster</span>
                    )}
                    {farmer.other_clusters.map(oc => (
                      <span key={oc.id} style={{
                        background: '#fef9c3', color: '#854d0e',
                        fontSize: '0.7rem', padding: '1px 7px', borderRadius: '999px',
                      }}>{oc.name}</span>
                    ))}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: '2px' }}>
                    {farmer.phone_number} · {farmer.location}
                  </div>
                </div>
                <button
                  onClick={() => setExpandedFarmer(
                    expandedFarmer === farmer.farmer_id ? null : farmer.farmer_id
                  )}
                  style={{
                    background: '#f3f4f6', border: 'none', cursor: 'pointer',
                    borderRadius: '6px', padding: '4px 10px', fontSize: '0.8rem',
                    color: '#374151',
                  }}
                >
                  {expandedFarmer === farmer.farmer_id ? '▲ Plots' : '▼ Plots'}
                </button>
              </div>

              {/* Plots */}
              {expandedFarmer === farmer.farmer_id && (
                <div style={{ borderTop: '1px solid #f3f4f6', background: '#fafafa', padding: '0.6rem 1rem' }}>
                  {farmer.plots.length === 0 ? (
                    <p style={{ fontSize: '0.8rem', color: '#9ca3af' }}>No plots found</p>
                  ) : farmer.plots.map(plot => (
                    <div key={plot.plot_id} style={{
                      display: 'flex', alignItems: 'center', gap: '10px',
                      padding: '0.4rem 0', borderBottom: '1px solid #f3f4f6',
                    }}>
                      <input
                        type="checkbox"
                        checked={plot.in_this_cluster || (selectedPlots[farmer.farmer_id]?.has(plot.plot_id) ?? false)}
                        disabled={plot.in_this_cluster}
                        onChange={() => togglePlot(farmer.farmer_id, plot.plot_id)}
                        style={{ accentColor: '#14b8a6', width: '15px', height: '15px' }}
                      />
                      <div style={{ flex: 1 }}>
                        <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#1f2937' }}>
                          {plot.name}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: '#6b7280', marginLeft: '6px' }}>
                          {plot.area_acres}ac · {plot.crop_name}
                        </span>
                        {plot.in_this_cluster && (
                          <span style={{
                            marginLeft: '6px', fontSize: '0.68rem',
                            background: '#dcfce7', color: '#15803d',
                            padding: '1px 6px', borderRadius: '999px',
                          }}>In cluster</span>
                        )}
                        {plot.other_clusters.map(oc => (
                          <span key={oc.id} style={{
                            marginLeft: '4px', fontSize: '0.68rem',
                            background: '#fef9c3', color: '#854d0e',
                            padding: '1px 6px', borderRadius: '999px',
                          }}>{oc.name}</span>
                        ))}
                      </div>
                    </div>
                  ))}

                  {/* Add button */}
                  <button
                    disabled={
                      saving ||
                      farmer.in_this_cluster && farmer.plots.every(p => p.in_this_cluster)
                    }
                    onClick={() => handleAddFarmer(farmer)}
                    style={{
                      marginTop: '0.6rem', background: '#14b8a6', color: '#fff',
                      border: 'none', borderRadius: '7px', padding: '6px 16px',
                      fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer',
                      opacity: saving ? 0.7 : 1,
                    }}
                  >
                    {saving ? 'Adding...' : `Add to ${clusterName}`}
                  </button>
                </div>
              )}
            </div>
          ))}

          {/* MUKKADAM RESULTS */}
          {!isFarmerMode && (results as MukkadamResult[]).map(m => (
            <div key={m.id} style={{
              border: '1.5px solid #e5e7eb', borderRadius: '10px',
              marginBottom: '0.75rem', padding: '0.75rem 1rem',
              background: m.in_this_cluster ? '#f0fdf4' : '#fff',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 700, color: '#111827' }}>{m.name}</span>
                  <span style={{
                    background: '#eff6ff', color: '#1d4ed8',
                    fontSize: '0.7rem', padding: '1px 7px', borderRadius: '999px',
                  }}>Crew: {m.crew_size}/{m.max_crew_capacity}</span>
                  {m.in_this_cluster && (
                    <span style={{
                      background: '#dcfce7', color: '#15803d',
                      fontSize: '0.7rem', fontWeight: 700,
                      padding: '1px 7px', borderRadius: '999px',
                    }}>✓ In this cluster</span>
                  )}
                  {m.other_clusters.map(oc => (
                    <span key={oc.id} style={{
                      background: '#fef9c3', color: '#854d0e',
                      fontSize: '0.7rem', padding: '1px 7px', borderRadius: '999px',
                    }}>{oc.name}</span>
                  ))}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: '3px' }}>
                  {m.mobile} · {m.village}, {m.district}
                </div>
                {m.activities.length > 0 && (
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '3px' }}>
                    Activities: {m.activities.map(a => a.name).join(', ')}
                  </div>
                )}
              </div>

              <button
                disabled={m.in_this_cluster || saving}
                onClick={() => handleAddMukkadam(m)}
                style={{
                  background: m.in_this_cluster ? '#e5e7eb' : '#14b8a6',
                  color: m.in_this_cluster ? '#9ca3af' : '#fff',
                  border: 'none', borderRadius: '7px', padding: '6px 14px',
                  fontSize: '0.82rem', fontWeight: 600,
                  cursor: m.in_this_cluster ? 'not-allowed' : 'pointer',
                  whiteSpace: 'nowrap', marginLeft: '12px',
                }}
              >
                {m.in_this_cluster ? '✓ Added' : saving ? 'Adding...' : 'Add'}
              </button>

              {!m.in_this_cluster && (
                <button
                  type="button"
                  onClick={() => handleInitiateEfficiencyEdit(m)}
                  style={{
                    background: '#f3f4f6', 
                    border: '1px solid #d1d5db',
                    padding: '6px', 
                    borderRadius: '6px', 
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                  title="Edit Efficiency"
                >
                  <Edit2 size={16} className="text-gray-600" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Confirm Modal (already in other cluster) */}
      {confirmPending && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          zIndex: 10001, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: '#fff', borderRadius: '12px', padding: '1.5rem',
            width: '380px', boxShadow: '0 20px 50px rgba(0,0,0,0.3)',
          }}>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#111827', marginBottom: '0.75rem' }}>
              Already in another cluster
            </div>
            <p style={{ fontSize: '0.88rem', color: '#374151', marginBottom: '0.5rem' }}>
              <strong>{confirmPending.name}</strong> is already in:
            </p>
            <div style={{ marginBottom: '1rem' }}>
              {confirmPending.otherClusters.map(oc => (
                <div key={oc.id} style={{
                  display: 'inline-block', background: '#fef9c3', color: '#854d0e',
                  padding: '2px 10px', borderRadius: '999px', fontSize: '0.8rem',
                  marginRight: '6px', marginBottom: '4px', fontWeight: 600,
                }}>
                  {oc.name}
                </div>
              ))}
            </div>
            <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '1.25rem' }}>
              Are you sure you want to also add to <strong>{clusterName}</strong>?
            </p>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button
                onClick={() => setConfirmPending(null)}
                style={{
                  flex: 1, padding: '0.6rem', border: '1.5px solid #e5e7eb',
                  borderRadius: '8px', background: '#fff', cursor: 'pointer',
                  fontSize: '0.88rem', color: '#374151',
                }}
              >Cancel</button>
              <button
                disabled={saving}
                onClick={() => {
                  if (confirmPending.type === 'farmer') {
                    doAddFarmer(confirmPending.id as string, confirmPending.plotIds || []);
                  } else {
                    doAddMukkadam(confirmPending.id as number);
                  }
                }}
                style={{
                  flex: 1, padding: '0.6rem', border: 'none',
                  borderRadius: '8px', background: '#14b8a6', color: '#fff',
                  cursor: 'pointer', fontSize: '0.88rem', fontWeight: 700,
                }}
              >
                {saving ? 'Adding...' : 'Yes, Add to Both'}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedMukkadamForEfficiency && (
  <div style={{
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    zIndex: 11000, display: 'flex', alignItems: 'center', justifyContent: 'center',
  }}>
    <div style={{ background: '#fff', borderRadius: '12px', width: '400px', overflow: 'hidden', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)' }}>
      <div style={{ padding: '1rem', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>Edit Efficiency: {selectedMukkadamForEfficiency.name}</h3>
        <button onClick={() => setSelectedMukkadamForEfficiency(null)} style={{ border: 'none', background: 'none', cursor: 'pointer' }}><X size={20}/></button>
      </div>
      
      <div style={{ padding: '1rem', maxHeight: '400px', overflowY: 'auto' }}>
        {editableActivities.map((act, idx) => (
          <div key={idx} style={{ marginBottom: '12px', padding: '12px', border: '1px solid #f1f5f9', borderRadius: '8px', background: '#f8fafc' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{act.name}</span>
              <button 
                onClick={() => handleSaveSingleEfficiency(act.rate_id, idx)}
                style={{ color: '#10b981', background: 'none', border: 'none', cursor: 'pointer' }}
                title="Save this activity"
              >
                <Save size={16} />
              </button>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 500 }}>Efficiency (ac/worker/day)</label>
              <input
                type="number"
                step="0.01"
                value={act.productivity}
                onChange={(e) => {
                  const updated = [...editableActivities];
                  updated[idx].productivity = parseFloat(e.target.value) || 0;
                  setEditableActivities(updated);
                }}
                style={{ width: '100%', padding: '8px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '0.9rem' }}
              />
            </div>
          </div>
        ))}
      </div>

      <div style={{ padding: '1rem', borderTop: '1px solid #e5e7eb', textAlign: 'right' }}>
        <button 
          onClick={() => setSelectedMukkadamForEfficiency(null)} 
          style={{ width: '100%', padding: '10px', background: '#334155', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}
        >
          Close Editor
        </button>
      </div>
    </div>
  </div>
)}
    </div>
  );
};


interface CreateClusterModalProps {
  states: StateOption[];
  onClose: () => void;
  onCreate: (cluster: Cluster) => void;
}

const CreateClusterModal: React.FC<CreateClusterModalProps> = ({
  states, onClose, onCreate,
}) => {
  const [newName, setNewName]                     = useState('');
  const [selectedState, setSelectedState]         = useState('MH');
  const [selectedLocations, setSelectedLocations] = useState<SelectedLocation[]>([]);
  const [loading, setLoading]                     = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedLocations.length === 0 || !newName.trim()) return;
    setLoading(true);
    try {
      const districtNames = [...new Set(selectedLocations.map(l => l.districtName).filter(Boolean))];
      const talukaNames   = [...new Set(selectedLocations.map(l => l.talukaName).filter(Boolean))];
      const villageNames  = selectedLocations.map(l => l.village.villagenameenglish);
      const districtCodes = [...new Set(selectedLocations.map(l => l.districtCode).filter(Boolean))];
      const talukaCodes   = [...new Set(selectedLocations.map(l => l.talukaCode).filter(Boolean))];
      const villageCodes  = selectedLocations.map(l => l.village.villagecode);

      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API_BASE_URL}/api/clusters/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({
          name: newName,
          state_code: selectedState,
          district_codes: districtCodes,
          taluka_codes: talukaCodes,
          village_codes: villageCodes,
          districts: districtNames,
          talukas: talukaNames,
          villages: villageNames,
        }),
      });
      const cluster = await res.json();
      onCreate(cluster);
    } finally {
      setLoading(false);
    }
  };

  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return ReactDOM.createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.4)' }}
      onClick={handleBackdrop}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col"
        style={{ maxHeight: '90vh' }}           // ✅ cap modal height
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header (fixed) ── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
          <h2 className="text-base font-bold text-slate-800">Create new cluster</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-400 transition"
          >
            ✕
          </button>
        </div>

        {/* ── Scrollable body ── */}
        <div className="overflow-y-auto flex-1 px-6 py-5">
          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Cluster name */}
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Cluster name
              </label>
              <input
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-300"
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="e.g. Satana North"
                autoFocus
              />
            </div>

            {/* State */}
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                State
              </label>
              <select
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-300"
                value={selectedState}
                onChange={e => {
                  setSelectedState(e.target.value);
                  setSelectedLocations([]);
                }}
              >
                <option value="">Select state</option>
                {states.map(s => (
                  <option key={s.state_code} value={s.state_code}>
                    {s.state_name_english}
                  </option>
                ))}
              </select>
            </div>

            {/* Villages */}
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Villages
              </label>
              {selectedState ? (
                // ✅ position:relative container so dropdown anchors inside modal scroll area
                <div className="relative">
                  <LocationSearch
                    key={selectedState}
                    stateCode={selectedState}
                    onSelectionChange={setSelectedLocations}
                  />
                </div>
              ) : (
                <p className="text-[13px] text-slate-400 mt-1">Select a state first</p>
              )}
            </div>

            {/* Extra bottom padding so dropdown has room to expand downward */}
            <div style={{ paddingBottom: '220px' }} />

          </form>
        </div>

        {/* ── Footer with submit (fixed at bottom) ── */}
        <div className="px-6 py-4 border-t border-slate-100 shrink-0">
          <button
            type="button"
            onClick={handleSubmit as any}
            disabled={loading || !newName.trim() || selectedLocations.length === 0}
            className="w-full py-2.5 bg-emerald-600 text-white text-sm font-bold rounded-xl hover:bg-emerald-700 disabled:opacity-40 transition"
          >
            {loading ? 'Creating...' : '+ Create & open'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

const TenderFront: React.FC = () => {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState(false);
  const [newName, setNewName] = useState('Satana');
  const [states, setStates] = useState<StateOption[]>([]);
  const [selectedState, setSelectedState] = useState<string>('MH');
  const [selectedLocations, setSelectedLocations] = useState<SelectedLocation[]>([]);
  const [showCalendar, setShowCalendar] = useState(false);
  const [calendarClusterId, setCalendarClusterId] = useState<number | null>(null);
  const [calendarClusterName, setCalendarClusterName] = useState('');

// STEP A: Add modal state (alongside your existing state declarations)
const [showCreateModal, setShowCreateModal] = useState(false);

  const [editModal, setEditModal] = useState<Cluster | null>(null);


  const [searchTerm, setSearchTerm] = useState('');
const [searchLoading, setSearchLoading] = useState(false);

const fetchClusters = useCallback(async (q: string) => {
  setLoading(true);
  setSearchLoading(true);
  try {
    const params = new URLSearchParams();
    if (q.trim()) params.append('q', q.trim());
    const res = await fetch(`${API_BASE_URL}/api/clusters/?${params.toString()}`);
    const data = await res.json();
    setClusters(data);
  } finally {
    setLoading(false);
    setSearchLoading(false);
  }
}, []);

useEffect(() => {
  fetchClusters('');
  // loadStates stays same
}, [fetchClusters]);
useEffect(() => {
  const id = setTimeout(() => {
    fetchClusters(searchTerm);
  }, 300); // 300ms debounce

  return () => clearTimeout(id);
}, [searchTerm, fetchClusters]);


  const [addModal, setAddModal] = useState<{
    clusterId: number;
    clusterName: string;
    mode: 'farmer' | 'mukkadam';
  } | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    const loadClusters = async () => {
      setLoading(true);
      try {
        const res  = await fetch(`${API_BASE_URL}/api/clusters/`);
        const data = await res.json();
        setClusters(data);
      } finally {
        setLoading(false);
      }
    };
    const loadStates = async () => {
      const res  = await fetch(`${API_BASE_URL}/locations/states/`);
      const data = await res.json();
      setStates(data);
    };
    loadClusters();
    loadStates();
  }, []);

  const handleCreateCluster = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedLocations.length === 0) return;
    setLoading(true);
    try {
      const districtNames = [...new Set(selectedLocations.map(l => l.districtName).filter(Boolean))];
      const talukaNames   = [...new Set(selectedLocations.map(l => l.talukaName).filter(Boolean))];
      const villageNames  = selectedLocations.map(l => l.village.villagenameenglish);
      const districtCodes = [...new Set(selectedLocations.map(l => l.districtCode).filter(Boolean))];
      const talukaCodes   = [...new Set(selectedLocations.map(l => l.talukaCode).filter(Boolean))];
      const villageCodes  = selectedLocations.map(l => l.village.villagecode);

      const token = localStorage.getItem('auth_token');

    const res = await fetch(`${API_BASE_URL}/api/clusters/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Token ${token}` } : {}),
      },
        body: JSON.stringify({
          name: newName,
          state_code: selectedState,
          district_codes: districtCodes,
          taluka_codes: talukaCodes,
          village_codes: villageCodes,
          districts: districtNames,
          talukas: talukaNames,
          villages: villageNames,
        }),
      });
      const cluster = await res.json();
      setClusters(prev => [...prev, cluster]);
      // ✅ Navigate directly to new cluster page
      navigate(`/cluster/${cluster.id}`);
    } finally {
      setLoading(false);
    }
  };
return (
  <div className="min-h-screen bg-slate-50 px-6 py-5">
    {/* Top bar */}


<div className="flex items-center justify-between mb-4">
  {/* Left: Go to Data */}


  {/* Right: three buttons grouped */}
  <div className="flex items-center gap-2">
    <button
      onClick={() => navigate('/global')}   // ← update route as needed
      className="flex items-center gap-2 px-5 py-2.5 bg-purple-500 text-white text-sm font-bold rounded-xl hover:bg-purple-600 transition shadow-sm whitespace-nowrap"
    >
      🌍 Global
    </button>

    <button
      onClick={() => navigate('/data')}
      className="flex items-center gap-2 px-5 py-2.5 bg-sky-500 text-white text-sm font-bold rounded-xl hover:bg-sky-600 transition shadow-sm whitespace-nowrap"
    >
      📊 Go to Data
    </button>

    <button
      onClick={() => setShowCreateModal(true)}
      className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 text-white text-sm font-bold rounded-xl hover:bg-emerald-700 transition shadow-sm whitespace-nowrap"
    >
      <span className="text-lg leading-none">+</span>
      New Cluster
    </button>
  </div>
</div>

    {/* Title + search */}
    <div className="mb-4">
      <h1 className="text-xl font-semibold text-slate-800">Choose cluster</h1>
      <div className="mt-3 max-w-xl">
        <input
          type="text"
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-300 focus:border-emerald-400"
          placeholder="Search by cluster, farmer, mukkadam..."
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
        />
      </div>

      
    </div>

    <div className="grid grid-cols-[minmax(0,2.2fr)_minmax(0,1.1fr)] gap-6 items-start">
      
      <section className="space-y-4">
        {clusters.length === 0 && !loading && (
          <p className="text-sm text-slate-400 italic">No clusters yet.</p>
        )}

{clusters.map(c => (
  <div
    key={c.id}
    className="rounded-2xl bg-white border border-slate-200 px-5 py-4 flex flex-col lg:flex-row items-center justify-between gap-6"
  >
    {/* ── Left: info ── */}
    <button
      className="flex-1 text-left w-full"
      onClick={() => navigate(`/cluster/${c.id}`)}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">

          {/* Name */}
          <div className="text-base font-semibold text-slate-900">{c.name}</div>

          {/* Farmers · Mukkadams */}
          <div className="mt-0.5 text-xs text-slate-500">
            {c.farmer_count} farmers · {c.mukkadam_count} mukkadams
          </div>

          {/* Location */}
          <div className="mt-0.5 text-xs text-slate-500">
            {[c.district, c.taluka, c.village].filter(Boolean).join(' · ')}
          </div>

          {/* Date range */}
          {c.date_range?.start_date && (
            <div className="mt-1 text-[11px] text-slate-400">
              {c.date_range.start_date} → {c.date_range.end_date || '?'}
            </div>
          )}
        </div>

        {/* ── Right: stats pills ── */}
        <div className="flex flex-col items-end gap-1.5 shrink-0">

          {/* Activities pill */}
          <span className="inline-flex items-center gap-1 rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-[11px] font-semibold text-violet-700 whitespace-nowrap">
            📋 {c.activity_count ?? 0} activities
          </span>

          {/* Allocations pill */}
          <span className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold text-sky-700 whitespace-nowrap">
            👷 {c.allocation_count ?? 0} allocations
          </span>

        </div>
      </div>
    </button>

    {/* ── Right: action buttons ── */}
    <div className="grid grid-cols-3 gap-2 w-full lg:w-auto">
      <button
        className="flex flex-col items-center justify-center rounded-xl border border-slate-100 bg-slate-50 px-4 py-2 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
        onClick={() => setAddModal({ clusterId: c.id, clusterName: c.name, mode: 'farmer' })}
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 mb-1">
          <User size={16} />
        </span>
        <span>Farmer</span>
      </button>

      <button
        className="flex flex-col items-center justify-center rounded-xl border border-slate-100 bg-slate-50 px-4 py-2 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
        onClick={() => setEditModal(c)}
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-50 text-indigo-600 mb-1">
          <Edit2 size={16} />
        </span>
        <span>Edit</span>
      </button>

      <button
        className="flex flex-col items-center justify-center rounded-xl border border-slate-100 bg-slate-50 px-4 py-2 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
        onClick={() => {
          setCalendarClusterId(c.id);
          setCalendarClusterName(c.name);
          setShowCalendar(true);
        }}
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-50 text-sky-600 mb-1">
          <Calendar size={16} />
        </span>
        <span>Calendar</span>
      </button>
    </div>
  </div>
))}
      </section>
{/* 
      <section className="cluster-form-section bg-white rounded-2xl border border-slate-200 shadow-sm px-4 py-4">
        <h2 className="text-sm font-semibold text-slate-800 mb-3">
          Create new cluster
        </h2>
        <form onSubmit={handleCreateCluster} className="cluster-form">
          <label className="form-label">
            Cluster name
            <input
              className="form-input"
              value={newName}
              onChange={e => setNewName(e.target.value)}
            />
          </label>

          <label className="form-label">
            State
            <select
              className="form-input"
              value={selectedState}
              onChange={e => {
                setSelectedState(e.target.value);
                setSelectedLocations([]);
              }}
            >
              <option value="">Select state</option>
              {states.map(s => (
                <option key={s.state_code} value={s.state_code}>
                  {s.state_name_english}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Villages
            {selectedState ? (
              <LocationSearch
                key={selectedState}
                stateCode={selectedState}
                onSelectionChange={setSelectedLocations}
              />
            ) : (
              <p className="mt-1 text-[13px] text-slate-400">
                Select a state first
              </p>
            )}
          </label>

          <button
            className="btn-primary full-width"
            type="submit"
            disabled={loading || !newName || selectedLocations.length === 0}
          >
            {loading ? 'Creating...' : '+ Create & open'}
          </button>
        </form>
      </section> */}
    </div>

    {showCalendar && calendarClusterId && (
      <ClusterActivityCalendar
        clusterId={calendarClusterId}
        clusterName={calendarClusterName}
        onClose={() => {
          setShowCalendar(false);
          setCalendarClusterId(null);
          setCalendarClusterName('');
        }}
      />
    )}

    {showCreateModal && (
      <CreateClusterModal
        states={states}
        onClose={() => setShowCreateModal(false)}
        onCreate={cluster => {
          setClusters(prev => [...prev, cluster]);
          setShowCreateModal(false);
          navigate(`/cluster/${cluster.id}`);
        }}
      />
    )}

    {editModal && (
      <EditClusterModal
        cluster={editModal}
        onClose={() => setEditModal(null)}
        onSaved={updated => {
          setClusters(prev =>
            prev.map(c => (c.id === updated.id ? updated : c)),
          );
          setEditModal(null);
        }}
      />
    )}

    {addModal && (
      <AddToClusterModal
        clusterId={addModal.clusterId}
        clusterName={addModal.clusterName}
        mode={addModal.mode}
        onClose={() => setAddModal(null)}
      />
    )}
  </div>
);

};


export default TenderFront;

