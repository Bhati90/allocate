// ManageMembersModal.tsx
import React, { useEffect, useState } from 'react';
import { X, Trash2, Loader2 } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

interface Farmer {
  farmer_id: string;
  farmer_name: string;
  phone_number: string;
  location: string;
}

interface Mukkadam {
  mukkadam_id: string;
  mukkadam_name: string;
  mukkadam_type: string;
}

interface Props {
  clusterId: number;
  clusterName: string;
  onClose: () => void;
  onMembersChanged: () => void; // refresh cluster list after removal
}

export const ManageMembersModal: React.FC<Props> = ({
  clusterId,
  clusterName,
  onClose,
  onMembersChanged,
}) => {
  const [farmers, setFarmers] = useState<Farmer[]>([]);
  const [mukkadams, setMukkadams] = useState<Mukkadam[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<string | null>(null); // id being removed
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE_URL}/api/clusters/${clusterId}/members/`);
        const data = await res.json();
        setFarmers(data.farmers ?? []);
        setMukkadams(data.mukkadams ?? []);
      } catch {
        setError('Failed to load members');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [clusterId]);

  const removeFarmer = async (farmerId: string) => {
    if (!confirm('Remove this farmer from the cluster?')) return;
    setRemoving(farmerId);
    try {
      const res = await fetch(`${API_BASE_URL}/api/clusters/${clusterId}/remove_farmer/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ farmer_id: farmerId }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.error ?? 'Failed to remove farmer');
        return;
      }
      setFarmers(prev => prev.filter(f => f.farmer_id !== farmerId));
      onMembersChanged();
    } finally {
      setRemoving(null);
    }
  };

  const removeMukkadam = async (mukkadamId: string) => {
    if (!confirm('Remove this mukkadam from the cluster?')) return;
    setRemoving(mukkadamId);
    try {
      const res = await fetch(`${API_BASE_URL}/api/clusters/${clusterId}/remove_mukkadam/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ mukkadam_id: mukkadamId }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.error ?? 'Failed to remove mukkadam');
        return;
      }
      setMukkadams(prev => prev.filter(m => m.mukkadam_id !== mukkadamId));
      onMembersChanged();
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <h2 className="text-base font-semibold text-slate-800">Manage Members</h2>
            <p className="text-xs text-slate-500 mt-0.5">{clusterName}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 hover:bg-slate-100 transition-colors"
          >
            <X size={18} className="text-slate-500" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 max-h-[60vh] overflow-y-auto space-y-5">
          {error && (
            <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 size={24} className="animate-spin text-slate-400" />
            </div>
          ) : (
            <>
              {/* Farmers */}
              <section>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                  Farmers ({farmers.length})
                </h3>
                {farmers.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No farmers assigned</p>
                ) : (
                  <ul className="space-y-1.5">
                    {farmers.map(f => (
                      <li
                        key={f.farmer_id}
                        className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"
                      >
                        <div>
                          <p className="text-sm font-medium text-slate-800">{f.farmer_name}</p>
                          <p className="text-[11px] text-slate-400">{f.phone_number || f.location || f.farmer_id}</p>
                        </div>
                        <button
                          onClick={() => removeFarmer(f.farmer_id)}
                          disabled={removing === f.farmer_id}
                          className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold text-red-600 bg-red-50 hover:bg-red-100 transition-colors disabled:opacity-50"
                        >
                          {removing === f.farmer_id
                            ? <Loader2 size={12} className="animate-spin" />
                            : <Trash2 size={12} />
                          }
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* Mukkadams */}
              <section>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                  Mukkadams ({mukkadams.length})
                </h3>
                {mukkadams.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No mukkadams assigned</p>
                ) : (
                  <ul className="space-y-1.5">
                    {mukkadams.map(m => (
                      <li
                        key={m.mukkadam_id}
                        className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"
                      >
                        <div>
                          <p className="text-sm font-medium text-slate-800">{m.mukkadam_name}</p>
                          <p className="text-[11px] text-slate-400 capitalize">{m.mukkadam_type}</p>
                        </div>
                        <button
                          onClick={() => removeMukkadam(m.mukkadam_id)}
                          disabled={removing === m.mukkadam_id}
                          className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold text-red-600 bg-red-50 hover:bg-red-100 transition-colors disabled:opacity-50"
                        >
                          {removing === m.mukkadam_id
                            ? <Loader2 size={12} className="animate-spin" />
                            : <Trash2 size={12} />
                          }
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 rounded-xl hover:bg-slate-200 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};