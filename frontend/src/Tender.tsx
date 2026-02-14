// App.tsx (TenderFront)
import React, { useEffect, useState } from 'react';
import FarmScheduler from './Farm';
// import ClusterActivityCalendar from './ClusterCalendar';
import ClusterActivityCalendar from './ClusterCalender';
import { API_BASE_URL } from './types/config';
import './Farm.css';

interface Cluster {
  id: number;
  name: string;
  district?: string;
  taluka?: string;
  village?: string;
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
  const [selectedDistrict, setSelectedDistrict] = useState<string>('');
  const [selectedTaluka, setSelectedTaluka] = useState<string>('');
  const [selectedVillage, setSelectedVillage] = useState<string>('');

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
      setSelectedDistrict('');
      setTalukas([]);
      setVillages([]);
      setSelectedTaluka('');
      setSelectedVillage('');
      return;
    }

    const loadDistricts = async () => {
      const res = await fetch(
        `${API_BASE_URL}/locations/districts/?state_code=${selectedState}`
      );
      const data = await res.json();
      setDistricts(data);
      setSelectedDistrict('');
      setTalukas([]);
      setVillages([]);
      setSelectedTaluka('');
      setSelectedVillage('');
    };

    loadDistricts();
  }, [selectedState]);

  // load talukas when district changes
  useEffect(() => {
    if (!selectedState || !selectedDistrict) {
      setTalukas([]);
      setSelectedTaluka('');
      setVillages([]);
      setSelectedVillage('');
      return;
    }

    const loadTalukas = async () => {
      const res = await fetch(
        `${API_BASE_URL}/locations/talukas/?state_code=${selectedState}&district_code=${selectedDistrict}`
      );
      const data = await res.json();
      setTalukas(data);
      setSelectedTaluka('');
      setVillages([]);
      setSelectedVillage('');
    };

    loadTalukas();
  }, [selectedState, selectedDistrict]);

  // load villages when taluka changes
  useEffect(() => {
    if (!selectedState || !selectedTaluka) {
      setVillages([]);
      setSelectedVillage('');
      return;
    }

    const loadVillages = async () => {
      const res = await fetch(
        `${API_BASE_URL}/locations/villages/?state_code=${selectedState}&taluka_code=${selectedTaluka}`
      );
      const data = await res.json();
      setVillages(data);
      setSelectedVillage('');
    };

    loadVillages();
  }, [selectedState, selectedTaluka]);

  const handleCreateCluster = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const districtObj = districts.find((d) => d.districtcode === selectedDistrict);
      const talukaObj = talukas.find((t) => t.subdistrictcode === selectedTaluka);
      const villageObj = villages.find((v) => v.villagecode === selectedVillage);

      const res = await fetch(`${API_BASE_URL}/api/clusters/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName,
          state_code: selectedState,
          district_code: selectedDistrict,
          taluka_code: selectedTaluka,
          village_code: selectedVillage,
          district: districtObj?.districtnameenglish ?? '',
          taluka: talukaObj?.subdistrictnameenglish ?? '',
          village: villageObj?.villagenameenglish ?? '',
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

              <label className="form-label">
                District
                <select
                  className="form-input"
                  value={selectedDistrict}
                  onChange={(e) => setSelectedDistrict(e.target.value)}
                  disabled={!selectedState || districts.length === 0}
                >
                  <option value="">Select district</option>
                  {districts.map((d) => (
                    <option key={d.districtcode} value={d.districtcode}>
                      {d.districtnameenglish}
                    </option>
                  ))}
                </select>
              </label>

              <label className="form-label">
                Taluka
                <select
                  className="form-input"
                  value={selectedTaluka}
                  onChange={(e) => setSelectedTaluka(e.target.value)}
                  disabled={!selectedDistrict || talukas.length === 0}
                >
                  <option value="">Select taluka</option>
                  {talukas.map((t) => (
                    <option key={t.subdistrictcode} value={t.subdistrictcode}>
                      {t.subdistrictnameenglish}
                    </option>
                  ))}
                </select>
              </label>

              <label className="form-label">
                Village
                <select
                  className="form-input"
                  value={selectedVillage}
                  onChange={(e) => setSelectedVillage(e.target.value)}
                  disabled={!selectedTaluka || villages.length === 0}
                >
                  <option value="">Select village</option>
                  {villages.map((v) => (
                    <option key={v.villagecode} value={v.villagecode}>
                      {v.villagelocalname || v.villagenameenglish}
                    </option>
                  ))}
                </select>
              </label>

              <button
                className="btn-primary full-width"
                type="submit"
                disabled={loading || !newName || !selectedVillage}
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
