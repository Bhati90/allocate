// App.tsx (TenderFront)
import React, { useEffect, useState } from 'react';
import FarmScheduler from './Farm';
import ClusterActivityCalendar from './ClusterCalender';
import { API_BASE_URL } from './types/config';
import './Farm.css';

interface Cluster {
  id: number;
  name: string;
  district?: string;
  taluka?: string;
  village?: string;
  districts?: string[];
  talukas?: string[];
  villages?: string[];
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
}

interface VillageOption {
  villagecode: string;
  villagenameenglish: string;
  villagelocalname: string;
}

const TenderFront: React.FC = () => {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  const [newName, setNewName] = useState('Satana');

  const [states, setStates] = useState<StateOption[]>([]);
  const [districts, setDistricts] = useState<DistrictOption[]>([]);
  const [talukas, setTalukas] = useState<TalukaOption[]>([]);
  const [villages, setVillages] = useState<VillageOption[]>([]);

  const [selectedState, setSelectedState] = useState<string>('MH');
  
  // Change to arrays for multi-select
  const [selectedDistricts, setSelectedDistricts] = useState<string[]>([]);
  const [selectedTalukas, setSelectedTalukas] = useState<string[]>([]);
  const [selectedVillages, setSelectedVillages] = useState<string[]>([]);

  // Calendar modal state
  const [showCalendar, setShowCalendar] = useState(false);
  const [calendarClusterId, setCalendarClusterId] = useState<number | null>(null);
  const [calendarClusterName, setCalendarClusterName] = useState('');

  // load clusters + states
  useEffect(() => {
    const loadClusters = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE_URL}/api/clusters/`);
        const data = await res.json();
        setClusters(data);
      } finally {
        setLoading(false);
      }
    };

    const loadStates = async () => {
      const res = await fetch(`${API_BASE_URL}/locations/states/`);
      const data = await res.json();
      setStates(data);
    };

    loadClusters();
    loadStates();
  }, []);

  // load districts when state changes
  useEffect(() => {
    if (!selectedState) {
      setDistricts([]);
      setSelectedDistricts([]);
      setTalukas([]);
      setVillages([]);
      setSelectedTalukas([]);
      setSelectedVillages([]);
      return;
    }

    const loadDistricts = async () => {
      const res = await fetch(
        `${API_BASE_URL}/locations/districts/?state_code=${selectedState}`
      );
      const data = await res.json();
      setDistricts(data);
      setSelectedDistricts([]);
      setTalukas([]);
      setVillages([]);
      setSelectedTalukas([]);
      setSelectedVillages([]);
    };

    loadDistricts();
  }, [selectedState]);

  // load talukas when districts change
  useEffect(() => {
    if (!selectedState || selectedDistricts.length === 0) {
      setTalukas([]);
      setSelectedTalukas([]);
      setVillages([]);
      setSelectedVillages([]);
      return;
    }

    const loadTalukas = async () => {
      // Fetch talukas for all selected districts
      const allTalukas: TalukaOption[] = [];
      
      for (const districtCode of selectedDistricts) {
        const res = await fetch(
          `${API_BASE_URL}/locations/talukas/?state_code=${selectedState}&district_code=${districtCode}`
        );
        const data = await res.json();
        allTalukas.push(...data);
      }
      
      // Remove duplicates based on subdistrictcode
      const uniqueTalukas = Array.from(
        new Map(allTalukas.map(t => [t.subdistrictcode, t])).values()
      );
      
      setTalukas(uniqueTalukas);
      setSelectedTalukas([]);
      setVillages([]);
      setSelectedVillages([]);
    };

    loadTalukas();
  }, [selectedState, selectedDistricts]);

  // load villages when talukas change
  useEffect(() => {
    if (!selectedState || selectedTalukas.length === 0) {
      setVillages([]);
      setSelectedVillages([]);
      return;
    }

    const loadVillages = async () => {
      // Fetch villages for all selected talukas
      const allVillages: VillageOption[] = [];
      
      for (const talukaCode of selectedTalukas) {
        const res = await fetch(
          `${API_BASE_URL}/locations/villages/?state_code=${selectedState}&taluka_code=${talukaCode}`
        );
        const data = await res.json();
        allVillages.push(...data);
      }
      
      // Remove duplicates based on villagecode
      const uniqueVillages = Array.from(
        new Map(allVillages.map(v => [v.villagecode, v])).values()
      );
      
      setVillages(uniqueVillages);
      setSelectedVillages([]);
    };

    loadVillages();
  }, [selectedState, selectedTalukas]);

  const handleDistrictChange = (districtCode: string) => {
    setSelectedDistricts(prev => {
      if (prev.includes(districtCode)) {
        return prev.filter(d => d !== districtCode);
      } else {
        return [...prev, districtCode];
      }
    });
  };

  const handleTalukaChange = (talukaCode: string) => {
    setSelectedTalukas(prev => {
      if (prev.includes(talukaCode)) {
        return prev.filter(t => t !== talukaCode);
      } else {
        return [...prev, talukaCode];
      }
    });
  };

  const handleVillageChange = (villageCode: string) => {
    setSelectedVillages(prev => {
      if (prev.includes(villageCode)) {
        return prev.filter(v => v !== villageCode);
      } else {
        return [...prev, villageCode];
      }
    });
  };

  const handleCreateCluster = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const districtNames = selectedDistricts
        .map(code => districts.find(d => d.districtcode === code)?.districtnameenglish)
        .filter(Boolean) as string[];
      
      const talukaNames = selectedTalukas
        .map(code => talukas.find(t => t.subdistrictcode === code)?.subdistrictnameenglish)
        .filter(Boolean) as string[];
      
      const villageNames = selectedVillages
        .map(code => villages.find(v => v.villagecode === code)?.villagenameenglish)
        .filter(Boolean) as string[];

      const res = await fetch(`${API_BASE_URL}/api/clusters/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName,
          state_code: selectedState,
          district_codes: selectedDistricts,
          taluka_codes: selectedTalukas,
          village_codes: selectedVillages,
          districts: districtNames,
          talukas: talukaNames,
          villages: villageNames,
        }),
      });

      const cluster = await res.json();
      setClusters((prev) => [...prev, cluster]);
      setSelectedClusterId(cluster.id);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCalendar = (clusterId: number, clusterName: string) => {
    setCalendarClusterId(clusterId);
    setCalendarClusterName(clusterName);
    setShowCalendar(true);
  };

  const handleCloseCalendar = () => {
    setShowCalendar(false);
    setCalendarClusterId(null);
    setCalendarClusterName('');
  };

  if (!selectedClusterId) {
    return (
      <div className="cluster-page">
        <header className="cluster-header">
          <h1>Choose cluster</h1>
        </header>

        <div className="cluster-layout">
          <section className="cluster-list-section">
            {clusters.length === 0 && !loading && (
              <p className="cluster-empty">No clusters yet.</p>
            )}

            {clusters.map((c) => (
              <div key={c.id} className="cluster-card-wrapper">
                <button
                  className="cluster-card"
                  onClick={() => setSelectedClusterId(c.id)}
                >
                  <div className="cluster-card-name">{c.name}</div>
                  <div className="cluster-card-meta">
                    {[c.district, c.taluka, c.village].filter(Boolean).join(' · ')}
                  </div>
                </button>
                <button
                  className="cluster-card-action"
                  onClick={() => handleOpenCalendar(c.id, c.name)}
                  title="View Activity Calendar"
                >
                  📅
                </button>
              </div>
            ))}
          </section>

          <section className="cluster-form-section">
            <h2>Create new cluster</h2>
            <form onSubmit={handleCreateCluster} className="cluster-form">
              <label className="form-label">
                Cluster name
                <input
                  className="form-input"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </label>

              <label className="form-label">
                State
                <select
                  className="form-input"
                  value={selectedState}
                  onChange={(e) => setSelectedState(e.target.value)}
                >
                  <option value="">Select state</option>
                  {states.map((s) => (
                    <option key={s.state_code} value={s.state_code}>
                      {s.state_name_english}
                    </option>
                  ))}
                </select>
              </label>

              {/* Multi-select Districts */}
              <label className="form-label">
                Districts ({selectedDistricts.length} selected)
                <div className="multi-select-container">
                  {districts.map((d) => (
                    <label key={d.districtcode} className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={selectedDistricts.includes(d.districtcode)}
                        onChange={() => handleDistrictChange(d.districtcode)}
                        disabled={!selectedState}
                      />
                      <span>{d.districtnameenglish}</span>
                    </label>
                  ))}
                  {districts.length === 0 && selectedState && (
                    <p className="empty-message">No districts available</p>
                  )}
                </div>
              </label>

              {/* Multi-select Talukas */}
              <label className="form-label">
                Talukas ({selectedTalukas.length} selected)
                <div className="multi-select-container">
                  {talukas.map((t) => (
                    <label key={t.subdistrictcode} className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={selectedTalukas.includes(t.subdistrictcode)}
                        onChange={() => handleTalukaChange(t.subdistrictcode)}
                        disabled={selectedDistricts.length === 0}
                      />
                      <span>{t.subdistrictnameenglish}</span>
                    </label>
                  ))}
                  {talukas.length === 0 && selectedDistricts.length > 0 && (
                    <p className="empty-message">No talukas available</p>
                  )}
                </div>
              </label>

              {/* Multi-select Villages */}
              <label className="form-label">
                Villages ({selectedVillages.length} selected)
                <div className="multi-select-container">
                  {villages.map((v) => (
                    <label key={v.villagecode} className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={selectedVillages.includes(v.villagecode)}
                        onChange={() => handleVillageChange(v.villagecode)}
                        disabled={selectedTalukas.length === 0}
                      />
                      <span>{v.villagelocalname || v.villagenameenglish}</span>
                    </label>
                  ))}
                  {villages.length === 0 && selectedTalukas.length > 0 && (
                    <p className="empty-message">No villages available</p>
                  )}
                </div>
              </label>

              <button
                className="btn-primary full-width"
                type="submit"
                disabled={loading || !newName || selectedVillages.length === 0}
              >
                + Create & open
              </button>
            </form>
          </section>
        </div>

        {/* Activity Calendar Modal */}
        {showCalendar && calendarClusterId && (
          <ClusterActivityCalendar
            clusterId={calendarClusterId}
            clusterName={calendarClusterName}
            onClose={handleCloseCalendar}
          />
        )}
      </div>
    );
  }

  return (
    <FarmScheduler
      clusterId={selectedClusterId}
      onBackToClusters={() => setSelectedClusterId(null)}
    />
  );
};

export default TenderFront;