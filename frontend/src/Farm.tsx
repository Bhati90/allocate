// FarmScheduler.tsx
import React, { useState, useEffect } from 'react';
import { Toaster, toast } from 'react-hot-toast';
import JobsPanel from './components/JobsPanel';
import CalendarPanel from './components/CalendarPanel';
import MukkadamPanel from './components/MukkadamPanel';
import AllocationModal from './components/AllocationModel';
import ProductivityWarningModal from './components/ProductivityWarning';
import { Job, Mukkadam, Allocation, ValidationResult } from './types/types';
import { API_BASE_URL } from './types/config';
import './Farm.css';
import JobDetailPanel from './components/JobDetail';

import { RefreshCw } from 'lucide-react';
import MukkadamDetailPanel from './components/MukkadamDetail';
type PotentialStatus = 'PARTIAL' | 'NONE';

interface PotentialJob {
  date: string;      
  cropName: string;
  variety: string;
  activityId: number;
  activityName: string;
  status: PotentialStatus;
  bookedArea: number;
  unbookedArea: number;
  bookedRate: number;
  clusterRate: number;
  farmerId: string;
  farmerName: string;
  plotId: number;
  plotName: string;
  potentialRevenue: number; // calculated as unbookedArea * max(clusterRate, bookedRate)
  jobId: string;
}

type PotentialByDate = Record<string, PotentialJob[]>;
// ─── Misc Costs Section ───────────────────────────────────
function MiscCostsSection({
  mukkadamId,
  jobId,
  initialCosts,
  onCostChange,
}: {
  mukkadamId: number;
  jobId: string;
  initialCosts: any[];
  onCostChange: () => void;
}) {
  const [costs, setCosts] = useState<any[]>(initialCosts);
  const [adding, setAdding] = useState(false);
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const handleAdd = async () => {
    if (!amount || parseFloat(amount) <= 0) { alert('Enter valid amount'); return; }
    if (!reason.trim()) { alert('Reason is required'); return; }
    setSaving(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamId}/job/${jobId}/misc/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount: parseFloat(amount), reason }),
        }
      );
      const data = await res.json();
      if (res.ok) {
        setCosts(prev => [data, ...prev]);
        setAmount('');
        setReason('');
        setAdding(false);
        onCostChange(); // refresh parent to update net_payable
      } else {
        alert(data.error);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (costId: number) => {
    if (!confirm('Remove this misc cost?')) return;
    setDeletingId(costId);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamId}/job/${jobId}/misc/${costId}/`,
        { method: 'DELETE' }
      );
      if (res.ok) {
        setCosts(prev => prev.filter(c => c.id !== costId));
        onCostChange();
      }
    } finally {
      setDeletingId(null);
    }
  };

  const total = costs.reduce((t, c) => t + c.amount, 0);

  return (
    <div style={{
      background: '#fafafa', borderRadius: '8px',
      border: '1px solid #e5e7eb', padding: '10px 12px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <p style={{ margin: 0, fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          ⚠ Miscellaneous Deductions
        </p>
        {!adding && (
          <button
            onClick={() => setAdding(true)}
            style={{
              fontSize: '0.68rem', padding: '3px 10px', borderRadius: '6px',
              border: '1px solid #e5e7eb', background: '#fff',
              color: '#374151', fontWeight: 600, cursor: 'pointer',
            }}
          >
            + Add
          </button>
        )}
      </div>

      {/* Add form */}
      {adding && (
        <div style={{
          background: '#fff', borderRadius: '8px', border: '1px solid #fde68a',
          padding: '10px', marginBottom: '8px',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px', marginBottom: '8px' }}>
            <div>
              <label style={{ fontSize: '0.65rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
                Amount (₹)
              </label>
              <input
                type="number"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                placeholder="0"
                style={{
                  width: '100%', padding: '6px 8px', border: '1px solid #e5e7eb',
                  borderRadius: '6px', fontSize: '0.82rem', fontWeight: 700,
                  boxSizing: 'border-box',
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.65rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
                Reason <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                type="text"
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="e.g. Tool damage, travel extra..."
                style={{
                  width: '100%', padding: '6px 8px', border: '1px solid #e5e7eb',
                  borderRadius: '6px', fontSize: '0.78rem', boxSizing: 'border-box',
                }}
              />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
            <button
              onClick={() => { setAdding(false); setAmount(''); setReason(''); }}
              style={{
                padding: '5px 12px', borderRadius: '6px', border: '1px solid #e5e7eb',
                background: '#f9fafb', fontSize: '0.72rem', cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleAdd}
              disabled={saving}
              style={{
                padding: '5px 12px', borderRadius: '6px', border: 'none',
                background: saving ? '#fde68a' : '#f59e0b',
                color: '#fff', fontSize: '0.72rem', fontWeight: 700,
                cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >
              {saving ? 'Saving...' : 'Add Deduction'}
            </button>
          </div>
        </div>
      )}

      {/* Costs list */}
      {costs.length === 0 ? (
        <p style={{ fontSize: '0.72rem', color: '#9ca3af', margin: 0, textAlign: 'center', padding: '8px 0' }}>
          No misc deductions added
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {costs.map((c, ci) => (
            <div key={c.id} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '6px 8px', borderRadius: '6px',
              background: '#fff', border: '1px solid #f3f4f6',
              fontSize: '0.74rem',
            }}>
              <div style={{ flex: 1 }}>
                <span style={{ color: '#374151', fontWeight: 600 }}>{c.reason}</span>
                <span style={{ color: '#9ca3af', fontSize: '0.62rem', marginLeft: '6px' }}>{c.created_at}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 800, color: '#dc2626' }}>
                  −₹{Number(c.amount).toLocaleString('en-IN')}
                </span>
                <button
                  onClick={() => handleDelete(c.id)}
                  disabled={deletingId === c.id}
                  style={{
                    padding: '2px 6px', borderRadius: '4px', border: 'none',
                    background: '#fef2f2', color: '#ef4444',
                    fontSize: '0.65rem', cursor: 'pointer', fontWeight: 700,
                  }}
                >
                  {deletingId === c.id ? '...' : '✕'}
                </button>
              </div>
            </div>
          ))}

          {/* Total */}
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            padding: '5px 8px', borderTop: '1.5px solid #e5e7eb', marginTop: '2px',
            fontSize: '0.74rem',
          }}>
            <span style={{ fontWeight: 700, color: '#374151' }}>Total Misc Deductions</span>
            <span style={{ fontWeight: 800, color: '#dc2626' }}>
              −₹{total.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

interface FarmSchedulerProps {clusterId: number;onBackToClusters: () => void;}
// ─── Payment Dashboard ────────────────────────────────────
function PaymentDashboard({ clusterId }: { clusterId: number }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'farmers' | 'mukkadams'>('farmers');
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [expandedAlloc, setExpandedAlloc] = useState<number | null>(null); // allocation detail expand

  // Farmer payment modal
  const [payModal, setPayModal] = useState<{
    farmerId: string; jobId: string;
    amount: number; farmerName: string;
  } | null>(null);
  const [payAmount, setPayAmount] = useState('');
  const [payMode, setPayMode] = useState('CASH');
  const [payNotes, setPayNotes] = useState('');
  const [payLoading, setPayLoading] = useState(false);

  // Mukkadam pay loading
  const [mukkadamPaying, setMukkadamPaying] = useState<string | null>(null);

  // Farmer verify loading
  const [verifyLoading, setVerifyLoading] = useState<number | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/cluster/${clusterId}/payment-dashboard/`);
      setData(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [clusterId]);

  const handleFarmerPay = async () => {
    if (!payModal || !payAmount || parseFloat(payAmount) <= 0) return;
    setPayLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/farmer/${payModal.farmerId}/job/${payModal.jobId}/payment/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount: parseFloat(payAmount), mode: payMode, notes: payNotes }),
        }
      );
      const result = await res.json();
      if (res.ok) {
        alert(`✅ ${result.message}`);
        setPayModal(null);
        fetchData();
      } else {
        alert(`❌ ${result.error}`);
      }
    } finally {
      setPayLoading(false);
    }
  };

  const handleMukkadamPay = async (mukkadamId: number, jobId: string, amount: number, name: string) => {
    if (!confirm(`Pay ₹${amount.toLocaleString('en-IN')} to ${name} for job #${jobId}?`)) return;
    const key = `${mukkadamId}-${jobId}`;
    setMukkadamPaying(key);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamId}/settlement/${jobId}/pay/`,
        { method: 'POST' }
      );
      const result = await res.json();
      if (res.ok) { alert(`✅ ${result.message}`); fetchData(); }
      else { alert(`❌ ${result.error}`); }
    } finally {
      setMukkadamPaying(null);
    }
  };
const handleAddWeeklyPayment = async (mukkadamId: number, assignmentId: number, amount: number) => {
  try {
    const res = await fetch(`${API_BASE_URL}/api/weekly-payment/add/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        assignment_id: assignmentId,
        amount: amount,
        payment_date: new Date().toISOString().split('T')[0],
      }),
    });
    if (res.ok) {
      fetchData(); // refresh
    }
  } catch (e) {
    console.error(e);
  }
};
  const handleFarmerVerify = async (allocationId: number, farmerId: string, jobId: string, agreed: boolean, disputeReason?: string) => {
    if (!agreed && !disputeReason?.trim()) {
      const reason = window.prompt('Please enter dispute reason:');
      if (!reason?.trim()) return;
      disputeReason = reason;
    }
    setVerifyLoading(allocationId);
    try {
      const res = await fetch(`${API_BASE_URL}/api/farmer/verify-work/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          farmer_id: farmerId,
          allocation_id: allocationId,
          agreed,
          dispute_reason: disputeReason || '',
        }),
      });
      const result = await res.json();
      if (res.ok) {
        alert(agreed ? '✅ Work verified successfully' : '⚠️ Dispute recorded');
        fetchData();
      } else {
        alert(`❌ ${result.error}`);
      }
    } finally {
      setVerifyLoading(null);
    }
  };

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px', color: '#9ca3af' }}>
      <RefreshCw size={24} className="animate-spin" style={{ color: '#14b8a6', marginRight: '10px' }} />
      Loading payment data...
    </div>
  );

  if (!data) return null;

  const STATUS_META: Record<string, { bg: string; text: string; label: string }> = {
    paid:              { bg: '#dcfce7', text: '#16a34a', label: '✓ Paid' },
    calculated:        { bg: '#fef9c3', text: '#b45309', label: '⚠ Due' },
    no_payment_needed: { bg: '#dbeafe', text: '#1d4ed8', label: '✅ Credit' },
    payment_raised:    { bg: '#fce7f3', text: '#be185d', label: 'Raised' },
    pending:           { bg: '#f3f4f6', text: '#6b7280', label: 'Pending' },
  };

  // ── Farmer verify status badge ──────────────────────────
  const VerifyBadge = ({ status }: { status: string }) => {
    const map: Record<string, { bg: string; color: string; label: string }> = {
      not_submitted:        { bg: '#f3f4f6', color: '#6b7280',  label: '⏳ Not Submitted' },
      pending_your_response:{ bg: '#fef9c3', color: '#b45309',  label: '👀 Awaiting Your Response' },
      agreed:               { bg: '#dcfce7', color: '#16a34a',  label: '✅ You Agreed' },
      disputed:             { bg: '#fef2f2', color: '#dc2626',  label: '❌ Disputed' },
    };
    const m = map[status] || map.not_submitted;
    return (
      <span style={{
        fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px',
        fontWeight: 700, background: m.bg, color: m.color,
      }}>
        {m.label}
      </span>
    );
  };

  // ── Allocation day-end report card ──────────────────────
  const AllocReportCard = ({ act, farmerId }: { act: any; farmerId: string }) => {
    const isExpanded = expandedAlloc === act.allocation_id;
    const hasReport = act.report_submitted;
    const verifyStatus = !hasReport
      ? 'not_submitted'
      : act.farmer_agreed === null
      ? 'pending_your_response'
      : act.farmer_agreed
      ? 'agreed'
      : 'disputed';

    const areaDiff = hasReport && act.actual_area_done != null
      ? (act.actual_area_done - act.allocated_area).toFixed(2)
      : null;
    const areaDiffNum = areaDiff ? parseFloat(areaDiff) : 0;

    return (
      <div style={{
        border: `1px solid ${verifyStatus === 'pending_your_response' ? '#fde68a' : verifyStatus === 'disputed' ? '#fecaca' : verifyStatus === 'agreed' ? '#bbf7d0' : '#e5e7eb'}`,
        borderRadius: '8px', overflow: 'hidden', background: '#fff',
        marginBottom: '6px',
      }}>
        {/* Row header */}
        <div
          onClick={() => setExpandedAlloc(isExpanded ? null : act.allocation_id)}
          style={{
            display: 'grid',
            gridTemplateColumns: '1.5fr 1fr 1fr 1fr 1fr auto',
            gap: '8px', padding: '8px 12px',
            cursor: 'pointer', alignItems: 'center',
            fontSize: '0.74rem',
          }}
        >
          <div>
            <p style={{ margin: 0, fontWeight: 700, color: '#111827' }}>{act.activity_name}</p>
            <p style={{ margin: 0, fontSize: '0.62rem', color: '#9ca3af' }}>{act.plot_code || act.plot_name || '—'}</p>
          </div>

          {/* Planned */}
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.6rem', color: '#6b7280' }}>Planned</p>
            <p style={{ margin: 0, fontWeight: 700, color: '#374151' }}>{Number(act.allocated_area).toFixed(2)} ac</p>
            <p style={{ margin: 0, fontSize: '0.6rem', color: '#9ca3af' }}>{act.allocated_workers} workers</p>
          </div>

          {/* Actual */}
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.6rem', color: '#6b7280' }}>Actual</p>
            {hasReport ? (
              <>
                <p style={{ margin: 0, fontWeight: 700, color: areaDiffNum < 0 ? '#dc2626' : areaDiffNum > 0 ? '#0f766e' : '#374151' }}>
                  {Number(act.actual_area_done).toFixed(2)} ac
                </p>
                <p style={{ margin: 0, fontSize: '0.6rem', color: '#9ca3af' }}>{act.actual_crew_size} workers</p>
              </>
            ) : (
              <p style={{ margin: 0, color: '#9ca3af', fontSize: '0.68rem' }}>—</p>
            )}
          </div>

          {/* Variance */}
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.6rem', color: '#6b7280' }}>Variance</p>
            {areaDiff != null ? (
              <p style={{
                margin: 0, fontWeight: 800,
                color: areaDiffNum < 0 ? '#dc2626' : areaDiffNum > 0 ? '#0f766e' : '#6b7280',
              }}>
                {areaDiffNum > 0 ? '+' : ''}{areaDiff} ac
              </p>
            ) : (
              <p style={{ margin: 0, color: '#9ca3af', fontSize: '0.68rem' }}>—</p>
            )}
          </div>

          {/* Status */}
          <div style={{ textAlign: 'center' }}>
            <VerifyBadge status={verifyStatus} />
          </div>

          <span style={{ color: '#9ca3af', fontSize: '0.65rem' }}>{isExpanded ? '▲' : '▼'}</span>
        </div>

        {/* Expanded detail */}
        {isExpanded && (
          <div style={{ borderTop: '1px solid #f3f4f6', padding: '12px', background: '#fafafa' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '10px' }}>

              {/* Planned box */}
              <div style={{ background: '#eff6ff', borderRadius: '8px', padding: '10px 12px', fontSize: '0.72rem' }}>
                <p style={{ margin: '0 0 6px', fontSize: '0.62rem', fontWeight: 700, color: '#1d4ed8', textTransform: 'uppercase' }}>📋 Planned</p>
                {[
                  { label: 'Date', val: act.allocated_date },
                  { label: 'Area', val: `${Number(act.allocated_area).toFixed(2)} ac` },
                  { label: 'Workers', val: act.allocated_workers },
                  { label: 'Rate', val: `₹${Number(act.mukkadam_rate).toLocaleString('en-IN')}/ac` },
                  { label: 'Amount', val: `₹${Number(act.mukkadam_amount).toLocaleString('en-IN')}` },
                ].map((r, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                    <span style={{ color: '#6b7280' }}>{r.label}</span>
                    <span style={{ fontWeight: 600, color: '#111827' }}>{r.val}</span>
                  </div>
                ))}
              </div>

              {/* Mukkadam report box */}
              <div style={{
                background: hasReport ? '#f0fdf4' : '#f9fafb',
                borderRadius: '8px', padding: '10px 12px', fontSize: '0.72rem',
                border: hasReport ? '1px solid #bbf7d0' : '1px solid #e5e7eb',
              }}>
                <p style={{ margin: '0 0 6px', fontSize: '0.62rem', fontWeight: 700, color: hasReport ? '#16a34a' : '#6b7280', textTransform: 'uppercase' }}>
                  👷 Mukkadam Report {!hasReport && '(Pending)'}
                </p>
                {hasReport ? (
                  <>
                    {[
                      { label: 'Actual Area', val: `${Number(act.actual_area_done).toFixed(2)} ac` },
                      { label: 'Crew Showed', val: act.actual_crew_size },
                      { label: 'Start Time', val: act.actual_start_time ? new Date(act.actual_start_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—' },
                      { label: 'End Time', val: act.actual_end_time ? new Date(act.actual_end_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—' },
                      { label: 'Submitted', val: act.report_submitted_at ? new Date(act.report_submitted_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : '—' },
                    ].map((r, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                        <span style={{ color: '#6b7280' }}>{r.label}</span>
                        <span style={{ fontWeight: 600, color: '#111827' }}>{r.val}</span>
                      </div>
                    ))}
                    {/* Revised amount */}
                    {act.actual_area_done && (
                      <div style={{ borderTop: '1px solid #bbf7d0', marginTop: '5px', paddingTop: '5px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                        <span style={{ color: '#6b7280' }}>Revised Amt</span>
                        <span style={{ color: '#0f766e' }}>
                          ₹{(Number(act.actual_area_done) * Number(act.mukkadam_rate)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    )}
                  </>
                ) : (
                  <p style={{ color: '#9ca3af', fontSize: '0.7rem', margin: 0 }}>
                    Mukkadam hasn't submitted day-end report yet
                  </p>
                )}
              </div>

              {/* Farmer response box */}
              <div style={{
                background: verifyStatus === 'agreed' ? '#f0fdf4' : verifyStatus === 'disputed' ? '#fef2f2' : '#fffbeb',
                borderRadius: '8px', padding: '10px 12px', fontSize: '0.72rem',
                border: `1px solid ${verifyStatus === 'agreed' ? '#bbf7d0' : verifyStatus === 'disputed' ? '#fecaca' : '#fde68a'}`,
              }}>
                <p style={{ margin: '0 0 6px', fontSize: '0.62rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>
                  🌾 Your Response
                </p>

                {verifyStatus === 'not_submitted' && (
                  <p style={{ color: '#9ca3af', fontSize: '0.7rem', margin: 0 }}>
                    Waiting for mukkadam to submit report first
                  </p>
                )}

                {verifyStatus === 'pending_your_response' && (
                  <>
                    <p style={{ margin: '0 0 8px', fontSize: '0.7rem', color: '#374151' }}>
                      Mukkadam reported <strong>{Number(act.actual_area_done).toFixed(2)} ac</strong> done.
                      {areaDiffNum !== 0 && (
                        <span style={{ color: areaDiffNum < 0 ? '#dc2626' : '#0f766e', marginLeft: '4px' }}>
                          ({areaDiffNum > 0 ? '+' : ''}{areaDiff} vs planned)
                        </span>
                      )}
                    </p>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        onClick={() => handleFarmerVerify(act.allocation_id, farmerId, act.job_id, true)}
                        disabled={verifyLoading === act.allocation_id}
                        style={{
                          flex: 1, padding: '6px', borderRadius: '6px', border: 'none',
                          background: '#16a34a', color: '#fff',
                          fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer',
                        }}
                      >
                        {verifyLoading === act.allocation_id ? '...' : '✅ Agree'}
                      </button>
                      <button
                        onClick={() => handleFarmerVerify(act.allocation_id, farmerId, act.job_id, false)}
                        disabled={verifyLoading === act.allocation_id}
                        style={{
                          flex: 1, padding: '6px', borderRadius: '6px', border: 'none',
                          background: '#dc2626', color: '#fff',
                          fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer',
                        }}
                      >
                        {verifyLoading === act.allocation_id ? '...' : '❌ Dispute'}
                      </button>
                    </div>
                  </>
                )}

                {verifyStatus === 'agreed' && (
                  <>
                    <p style={{ margin: '0 0 4px', color: '#16a34a', fontWeight: 700, fontSize: '0.78rem' }}>
                      ✅ You agreed with the report
                    </p>
                    <p style={{ margin: 0, fontSize: '0.65rem', color: '#6b7280' }}>
                      Settlement will use actual area: <strong>{Number(act.actual_area_done).toFixed(2)} ac</strong>
                    </p>
                    {act.farmer_response_at && (
                      <p style={{ margin: '3px 0 0', fontSize: '0.6rem', color: '#9ca3af' }}>
                        Responded: {new Date(act.farmer_response_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                      </p>
                    )}
                  </>
                )}

                {verifyStatus === 'disputed' && (
                  <>
                    <p style={{ margin: '0 0 4px', color: '#dc2626', fontWeight: 700, fontSize: '0.78rem' }}>
                      ❌ You disputed this report
                    </p>
                    {act.farmer_dispute_reason && (
                      <p style={{ margin: '0 0 4px', fontSize: '0.68rem', color: '#374151', background: '#fef2f2', padding: '5px 7px', borderRadius: '5px' }}>
                        "{act.farmer_dispute_reason}"
                      </p>
                    )}
                    {act.farmer_response_at && (
                      <p style={{ margin: 0, fontSize: '0.6rem', color: '#9ca3af' }}>
                        Responded: {new Date(act.farmer_response_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                      </p>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Duration bar if both times present */}
            {act.actual_start_time && act.actual_end_time && (
              <div style={{ background: '#fff', borderRadius: '6px', border: '1px solid #e5e7eb', padding: '8px 12px', fontSize: '0.7rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ color: '#6b7280' }}>
                    🕐 {new Date(act.actual_start_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span style={{ fontWeight: 700, color: '#374151' }}>
                    {Math.round((new Date(act.actual_end_time).getTime() - new Date(act.actual_start_time).getTime()) / 60000)} mins worked
                  </span>
                  <span style={{ color: '#6b7280' }}>
                    🕐 {new Date(act.actual_end_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* ── Top Summary Bar ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '10px', padding: '14px 16px',
        borderBottom: '1px solid #e5e7eb', background: '#fff', flexShrink: 0,
      }}>
        {[
          { label: 'Farmers', value: data.farmer_count, suffix: 'in cluster', color: '#1d4ed8', bg: '#eff6ff', border: '#bfdbfe' },
          { label: 'To Collect', value: `₹${data.total_farmer_due.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, suffix: 'from farmers', color: '#b45309', bg: '#fffbeb', border: '#fde68a' },
          { label: 'Mukkadams', value: data.mukkadam_count, suffix: 'assigned', color: '#0f766e', bg: '#f0fdfa', border: '#99f6e4' },
         { 
  label: 'To Pay', 
  value: `₹${Math.max(0, data.mukkadams.reduce((sum: number, m: any) => {
    const totalNet = m.settlements.reduce((s: number, s2: any) => s + s2.net_payable, 0);
    return sum + totalNet;
  }, 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, 
  suffix: 'to mukkadams', 
  color: '#dc2626', 
  bg: '#fef2f2', 
  border: '#fecaca' 
}, ].map(s => (
          <div key={s.label} style={{ background: s.bg, borderRadius: '10px', border: `1.5px solid ${s.border}`, padding: '10px 14px' }}>
            <p style={{ margin: 0, fontSize: '0.65rem', color: '#6b7280', marginBottom: '3px' }}>{s.label}</p>
            <p style={{ margin: 0, fontWeight: 800, fontSize: '1.2rem', color: s.color, lineHeight: 1 }}>{s.value}</p>
            <p style={{ margin: '2px 0 0', fontSize: '0.62rem', color: '#9ca3af' }}>{s.suffix}</p>
          </div>
        ))}
      </div>

      {/* ── Tab Switch ── */}
      <div style={{ display: 'flex', borderBottom: '1.5px solid #e5e7eb', background: '#fff', flexShrink: 0 }}>
        {[
          { key: 'farmers', label: '🌾 Farmer Collections', count: data.farmers.length, color: '#3b82f6' },
          { key: 'mukkadams', label: '👷 Mukkadam Settlements', count: data.mukkadams.length, color: '#0f766e' },
        ].map(t => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key as any); setExpandedKey(null); setExpandedAlloc(null); }}
            style={{
              padding: '10px 20px', border: 'none', background: 'none', cursor: 'pointer',
              fontSize: '0.82rem', fontWeight: 700,
              borderBottom: tab === t.key ? `2.5px solid ${t.color}` : '2.5px solid transparent',
              color: tab === t.key ? t.color : '#6b7280',
            }}
          >
            {t.label}
            <span style={{
              marginLeft: '6px', fontSize: '0.65rem', padding: '1px 6px',
              borderRadius: '999px', background: tab === t.key ? t.color : '#f3f4f6',
              color: tab === t.key ? '#fff' : '#6b7280', fontWeight: 700,
            }}>
              {t.count}
            </span>
          </button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', paddingRight: '12px' }}>
          <button onClick={fetchData} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '6px 12px', borderRadius: '7px', border: 'none', background: '#f3f4f6', color: '#374151', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' }}>
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* ── Scrollable Content ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px' }}>

        {/* ════ FARMERS TAB ════ */}
        {tab === 'farmers' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {data.farmers.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af', fontSize: '0.82rem' }}>
                No farmer jobs found in this cluster
              </div>
            ) : data.farmers.map((f: any) => {
              const s = f.summary;
              const hasBalance = s.balance_due > 0.01;
              const expandKey = `farmer-${f.farmer_id}-${f.job_id}`;
              const isOpen = expandedKey === expandKey;

              // Count pending verifications for this farmer
              const pendingVerify = (f.activities || []).filter((a: any) =>
                a.report_submitted && a.farmer_agreed === null
              ).length;

              return (
                <div key={expandKey} style={{
                  border: `1.5px solid ${pendingVerify > 0 ? '#fde68a' : hasBalance ? '#fde68a' : s.all_activities_past ? '#bbf7d0' : '#e5e7eb'}`,
                  borderRadius: '12px', background: hasBalance ? '#fffbeb' : '#fff',
                  overflow: 'hidden',
                }}>
                  {/* Header */}
                  <div
                    onClick={() => setExpandedKey(isOpen ? null : expandKey)}
                    style={{ padding: '12px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div>
                        <p style={{ margin: 0, fontWeight: 700, fontSize: '0.88rem', color: '#111827' }}>{f.farmer_name}</p>
                        <p style={{ margin: 0, fontSize: '0.68rem', color: '#9ca3af' }}>
                          {f.farmer_id} · Job <span style={{ fontFamily: 'monospace', color: '#1d4ed8' }}>#{f.job_id}</span>
                        </p>
                      </div>
                      <span style={{
                        fontSize: '0.65rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 600,
                        background: hasBalance ? '#fef9c3' : s.all_activities_past ? '#dcfce7' : '#f3f4f6',
                        color: hasBalance ? '#b45309' : s.all_activities_past ? '#16a34a' : '#6b7280',
                      }}>
                        {hasBalance ? '⚠ Balance Due' : s.all_activities_past ? '✓ Complete' : '🕐 In Progress'}
                      </span>
                      {pendingVerify > 0 && (
                        <span style={{ fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: '#fef9c3', color: '#b45309' }}>
                          👀 {pendingVerify} Verification{pendingVerify > 1 ? 's' : ''} Pending
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ textAlign: 'right', fontSize: '0.72rem' }}>
                        <span style={{ color: '#6b7280' }}>Billed: </span>
                        <span style={{ fontWeight: 700, color: '#0f766e' }}>
                          ₹{s.total_billable_so_far.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </span>
                        <span style={{ color: '#6b7280', marginLeft: '8px' }}>Paid: </span>
                        <span style={{ fontWeight: 700, color: '#16a34a' }}>
                          ₹{s.total_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </span>
                        {hasBalance && <>
                          <span style={{ color: '#6b7280', marginLeft: '8px' }}>Due: </span>
                          <span style={{ fontWeight: 800, color: '#dc2626' }}>
                            ₹{s.balance_due.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </span>
                        </>}
                      </div>
                      {hasBalance && (
                        <button
                          onClick={e => {
                            e.stopPropagation();
                            setPayModal({ farmerId: f.farmer_id, jobId: f.job_id, amount: Math.round(s.balance_due), farmerName: f.farmer_name });
                            setPayAmount(String(Math.round(s.balance_due)));
                            setPayMode('CASH'); setPayNotes('');
                          }}
                          style={{ padding: '6px 12px', borderRadius: '7px', border: 'none', background: '#3b82f6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
                        >
                          + Collect
                        </button>
                      )}
                      <span style={{ color: '#9ca3af', fontSize: '0.65rem' }}>{isOpen ? '▲' : '▼'}</span>
                    </div>
                  </div>

                  {/* Expanded */}
                  {isOpen && (
                    <div style={{ borderTop: '1px solid #e5e7eb', padding: '14px 16px', background: '#fafafa' }}>

                      {/* ── Work Reports section ── */}
                      <p style={{ margin: '0 0 8px', fontSize: '0.68rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        📋 Work Allocations & Verification
                      </p>

                      {/* Column headers */}
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: '1.5fr 1fr 1fr 1fr 1fr auto',
                        gap: '8px', padding: '4px 12px',
                        fontSize: '0.6rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase',
                      }}>
                        <span>Activity / Plot</span>
                        <span style={{ textAlign: 'center' }}>Planned</span>
                        <span style={{ textAlign: 'center' }}>Actual</span>
                        <span style={{ textAlign: 'center' }}>Variance</span>
                        <span style={{ textAlign: 'center' }}>Status</span>
                        <span />
                      </div>

                      {(f.activities || []).flatMap((act: any) =>
  (act.allocations || [{ ...act, allocation_id: act.activity_id }]).map((alloc: any) => (
    <AllocReportCard
      key={alloc.allocation_id}
      act={{ ...act, ...alloc }}   // merge activity fields + allocation fields
      farmerId={f.farmer_id}
    />
  ))
)}

                      {/* ── Calculation + History ── */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', margin: '12px 0' }}>
                        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', padding: '10px 12px', fontSize: '0.76rem' }}>
                          <p style={{ margin: '0 0 8px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>💰 Calculation</p>
                          {[
                            { label: 'Total Billed So Far', val: `₹${s.total_billable_so_far.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e' },
                            { label: '− Advance Paid', val: `−₹${s.advance_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#16a34a' },
                            ...(s.additional_paid > 0 ? [{ label: '− Additional Collected', val: `−₹${s.additional_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#16a34a' }] : []),
                          ].map((row, ri) => (
                            <div key={ri} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                              <span style={{ color: '#6b7280' }}>{row.label}</span>
                              <span style={{ fontWeight: 700, color: row.color }}>{row.val}</span>
                            </div>
                          ))}
                          <div style={{ borderTop: '1.5px solid #e5e7eb', paddingTop: '6px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                            <span style={{ color: '#111827' }}>Balance Due</span>
                            <span style={{ color: hasBalance ? '#dc2626' : '#16a34a', fontSize: '0.9rem' }}>
                              {hasBalance ? `₹${s.balance_due.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '✓ Clear'}
                            </span>
                          </div>
                          {s.all_activities_past && s.final_gap > 0 && (
                            <div style={{ marginTop: '6px', padding: '6px 8px', borderRadius: '6px', background: '#fef2f2', border: '1px solid #fecaca', fontSize: '0.68rem', color: '#dc2626', fontWeight: 700 }}>
                              ⚠ All done — ₹{s.final_gap.toLocaleString('en-IN', { maximumFractionDigits: 0 })} vs booking total
                            </div>
                          )}
                        </div>

                        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', padding: '10px 12px', fontSize: '0.76rem' }}>
                          <p style={{ margin: '0 0 8px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📅 Payment History</p>
                          {f.payment_history.length === 0 ? (
                            <p style={{ color: '#9ca3af', fontSize: '0.72rem', margin: 0 }}>No payments recorded</p>
                          ) : (
                            <>
                              {f.payment_history.map((p: any, pi: number) => (
                                <div key={pi} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '4px', marginBottom: '4px', borderBottom: pi < f.payment_history.length - 1 ? '1px solid #f3f4f6' : 'none' }}>
                                  <div>
                                    <span style={{ fontSize: '0.6rem', padding: '1px 5px', borderRadius: '999px', marginRight: '5px', background: p.type === 'advance' ? '#eff6ff' : '#f0fdf4', color: p.type === 'advance' ? '#1d4ed8' : '#16a34a', fontWeight: 600 }}>{p.mode}</span>
                                    <span style={{ color: '#9ca3af', fontSize: '0.64rem' }}>{p.date}</span>
                                  </div>
                                  <span style={{ fontWeight: 700, color: '#16a34a' }}>₹{Number(p.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                                </div>
                              ))}
                              <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '5px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                                <span>Total</span>
                                <span style={{ color: '#16a34a' }}>₹{s.total_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                              </div>
                            </>
                          )}
                        </div>
                      </div>

                      {hasBalance && (
                        <button
                          onClick={() => {
                            setPayModal({ farmerId: f.farmer_id, jobId: f.job_id, amount: Math.round(s.balance_due), farmerName: f.farmer_name });
                            setPayAmount(String(Math.round(s.balance_due)));
                            setPayMode('CASH'); setPayNotes('');
                          }}
                          style={{ width: '100%', padding: '10px', borderRadius: '8px', border: 'none', background: '#3b82f6', color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' }}
                        >
                          + Collect ₹{Math.round(s.balance_due).toLocaleString('en-IN')} from {f.farmer_name}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ════ MUKKADAMS TAB ════ */}
        {tab === 'mukkadams' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {data.mukkadams.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af', fontSize: '0.82rem' }}>
                No mukkadams assigned to this cluster
              </div>
            ) : data.mukkadams.map((m: any) => {
              const expandKey = `mukkadam-${m.mukkadam_id}`;
              const isOpen = expandedKey === expandKey;
              const hasDue = m.summary.pending_payment > 0.01;

              return (
                <div key={expandKey} style={{ border: `1.5px solid ${hasDue ? '#fde68a' : '#e5e7eb'}`, borderRadius: '12px', background: hasDue ? '#fffbeb' : '#fff', overflow: 'hidden' }}>
                  <div onClick={() => setExpandedKey(isOpen ? null : expandKey)} style={{ padding: '12px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div>
                        <p style={{ margin: 0, fontWeight: 700, fontSize: '0.88rem', color: '#111827' }}>{m.mukkadam_name}</p>
                        <p style={{ margin: 0, fontSize: '0.68rem', color: '#9ca3af' }}>
                          {m.mobile} · Crew: {m.crew_size} · {m.summary.total_jobs} job{m.summary.total_jobs !== 1 ? 's' : ''}
                        </p>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ textAlign: 'right', fontSize: '0.72rem' }}>
                        {hasDue && <><span style={{ color: '#6b7280' }}>Pending: </span><span style={{ fontWeight: 800, color: '#dc2626' }}>{(() => {
  const totalNet = m.settlements.reduce((sum: number, s: any) => sum + s.net_payable, 0);
  return `₹${Math.max(0, totalNet).toLocaleString('en-IN')}`;
})()}</span></>}
                        {m.summary.total_paid_out > 0 && <><span style={{ color: '#6b7280', marginLeft: '8px' }}>Paid: </span><span style={{ fontWeight: 700, color: '#16a34a' }}>₹{m.summary.total_paid_out.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span></>}
                      </div>
                      <span style={{ color: '#9ca3af', fontSize: '0.65rem' }}>{isOpen ? '▲' : '▼'}</span>
                    </div>
                  </div>

                  {isOpen && (
                    <div style={{ borderTop: '1px solid #e5e7eb', padding: '14px 16px', background: '#fafafa', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {m.settlements.length === 0 ? (
                        <p style={{ fontSize: '0.78rem', color: '#9ca3af', margin: 0 }}>No settlements calculated yet</p>
                      ) : m.settlements.map((s: any) => {
                        const sm = STATUS_META[s.status] || STATUS_META.pending;
                        const needsPay = s.show_raise_payment;
                        const payKey = `${m.mukkadam_id}-${s.job_id}`;

                        return (
                          <div key={s.job_id} style={{ background: '#fff', borderRadius: '10px', border: `1px solid ${needsPay ? '#fde68a' : s.net_payable <= 0 ? '#bbf7d0' : '#e5e7eb'}`, padding: '12px 14px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                              <div>
                                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#1d4ed8', fontSize: '0.8rem' }}>#{s.job_id}</span>
                                <span style={{ marginLeft: '8px', fontSize: '0.78rem', color: '#374151', fontWeight: 600 }}>{s.farmer_name}</span>
                                <span style={{ marginLeft: '6px', fontSize: '0.65rem', color: '#9ca3af' }}>{s.farmer_id}</span>
                              </div>
                              <span style={{ fontSize: '0.65rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: sm.bg, color: sm.text }}>
                                {sm.label}
                              </span>
                            </div>

                            {/* Activity table with actual vs planned */}
                            <div style={{ border: '1px solid #e5e7eb', borderRadius: '7px', overflow: 'hidden', marginBottom: '10px' }}>
                              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
                                <thead>
                                  <tr style={{ background: '#f9fafb' }}>
                                    {['Activity', 'Plot', 'Date', 'Planned ac', 'Actual ac', 'Crew', 'Rate/ac', 'Amount', 'Farmer ✓'].map(h => (
                                      <th key={h} style={{ padding: '5px 8px', textAlign: ['Planned ac', 'Actual ac', 'Crew', 'Rate/ac', 'Amount'].includes(h) ? 'right' : 'left', color: '#6b7280', fontWeight: 600, fontSize: '0.62rem', borderBottom: '1px solid #e5e7eb' }}>{h}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {s.activities.map((act: any, idx: number) => {
                                    const hasActual = act.actual_area_done != null;
                                    const diff = hasActual ? (act.actual_area_done - act.allocated_area) : 0;
                                    const effectiveArea = act.use_actual_for_settlement && hasActual ? act.actual_area_done : act.allocated_area;
                                    const effectiveAmt = effectiveArea * act.mukkadam_rate;

                                    return (
                                      <tr key={idx} style={{ borderTop: idx > 0 ? '1px solid #f3f4f6' : 'none' }}>
                                        <td style={{ padding: '6px 8px', fontWeight: 600, color: '#111827' }}>{act.activity_name}</td>
                                        <td style={{ padding: '6px 8px', color: '#6b7280', fontFamily: 'monospace', fontSize: '0.66rem' }}>{act.plot_code}</td>
                                        <td style={{ padding: '6px 8px', color: '#374151', whiteSpace: 'nowrap' }}>{act.scheduled_date || '—'}</td>
                                        <td style={{ padding: '6px 8px', textAlign: 'right', color: '#6b7280' }}>{Number(act.allocated_area).toFixed(2)}</td>
                                        <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                                          {hasActual ? (
                                            <span style={{ fontWeight: 700, color: diff < 0 ? '#dc2626' : diff > 0 ? '#0f766e' : '#374151' }}>
                                              {Number(act.actual_area_done).toFixed(2)}
                                              {diff !== 0 && <span style={{ fontSize: '0.6rem', marginLeft: '2px' }}>({diff > 0 ? '+' : ''}{diff.toFixed(2)})</span>}
                                            </span>
                                          ) : <span style={{ color: '#9ca3af' }}>—</span>}
                                        </td>
                                        <td style={{ padding: '6px 8px', textAlign: 'right', color: '#6b7280' }}>
                                          {act.actual_crew_size ?? act.allocated_workers}
                                          {act.actual_crew_size != null && act.actual_crew_size !== act.allocated_workers && (
                                            <span style={{ fontSize: '0.58rem', color: '#9ca3af', marginLeft: '2px' }}>({act.allocated_workers} pln)</span>
                                          )}
                                        </td>
                                        <td style={{ padding: '6px 8px', textAlign: 'right', color: '#6b7280' }}>₹{Number(act.mukkadam_rate).toLocaleString('en-IN')}</td>
                                        <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: '#0f766e' }}>
                                          ₹{Number(effectiveAmt).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                          {act.use_actual_for_settlement && <span style={{ fontSize: '0.58rem', color: '#0f766e', marginLeft: '2px' }}>(actual)</span>}
                                        </td>
                                        <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                                          {act.farmer_agreed === true && <span style={{ color: '#16a34a', fontSize: '0.7rem' }}>✅</span>}
                                          {act.farmer_agreed === false && <span style={{ color: '#dc2626', fontSize: '0.7rem' }}>❌</span>}
                                          {act.farmer_agreed === null && act.report_submitted && <span style={{ color: '#b45309', fontSize: '0.7rem' }}>⏳</span>}
                                          {!act.report_submitted && <span style={{ color: '#9ca3af', fontSize: '0.7rem' }}>—</span>}
                                        </td>
                                      </tr>
                                    );
                                  })}
                                  <tr style={{ borderTop: '2px solid #e5e7eb', background: '#f0fdfa' }}>
                                    <td colSpan={3} style={{ padding: '6px 8px', fontWeight: 700, fontSize: '0.7rem' }}>Total</td>
                                    <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: '#6b7280' }}>
                                      {s.activities.reduce((t: number, a: any) => t + Number(a.allocated_area), 0).toFixed(2)}
                                    </td>
                                    <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700 }}>
                                      {s.activities.some((a: any) => a.actual_area_done != null)
                                        ? s.activities.reduce((t: number, a: any) => t + Number(a.actual_area_done ?? a.allocated_area), 0).toFixed(2)
                                        : '—'}
                                    </td>
                                    <td colSpan={2} />
                                    <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 800, color: '#0f766e' }}>
                                      ₹{s.gross_amount.toLocaleString('en-IN')}
                                    </td>
                                    <td />
                                  </tr>
                                </tbody>
                              </table>
                            </div>

                            {/* Settlement calc + weekly */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>
                              <div style={{ background: '#f9fafb', borderRadius: '8px', padding: '10px 12px', fontSize: '0.74rem' }}>
                                <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>💰 Settlement</p>
                                {[
                                  { label: 'Gross Earned', val: `₹${s.gross_amount.toLocaleString('en-IN')}`, color: '#0f766e' },
{ label: '− 10% Deposit', val: `−₹${s.deposit_held.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#b45309' },
{ label: '= 90% Payable', val: `₹${s.payable_90pct.toLocaleString('en-IN')}`, color: '#1f2937', bold: true },
...(s.deposit_carried_forward > 0 ? [{ label: '+ Deposit from prev job', val: `+₹${Number(s.deposit_carried_forward).toLocaleString('en-IN')}`, color: '#0f766e' }] : []),
...(s.advance_deducted > 0 ? [{ label: '− Advance', val: `−₹${s.advance_deducted.toLocaleString('en-IN')}`, color: '#dc2626' }] : []),
...(s.total_misc > 0 ? [{ label: '− Miscellaneous', val: `−₹${s.total_misc.toLocaleString('en-IN')}`, color: '#dc2626' }] : []),
...(s.weekly_payments_deducted > 0 ? [{ label: '− Weekly Payments', val: `−₹${s.weekly_payments_deducted.toLocaleString('en-IN')}`, color: '#dc2626' }] : []),
...(s.credit_carried_forward > 0 ? [{ label: '− Credit from prev job', val: `−₹${Number(s.credit_carried_forward).toLocaleString('en-IN')}`, color: '#dc2626' }] : []),].map((row: any, ri) => (
                                  <div key={ri} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                    <span style={{ color: '#6b7280' }}>{row.label}</span>
                                    <span style={{ fontWeight: row.bold ? 800 : 600, color: row.color }}>{row.val}</span>
                                  </div>
                                ))}
                                <div style={{ borderTop: '1.5px solid #e5e7eb', paddingTop: '5px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                                  <span style={{ color: '#111827' }}>Net Payable</span>
                                  <span style={{ color: s.net_payable > 0 ? '#dc2626' : '#16a34a', fontSize: '0.88rem' }}>
                                    {s.net_payable > 0 ? `₹${s.net_payable.toLocaleString('en-IN')}` : `−₹${Math.abs(s.net_payable).toLocaleString('en-IN')}`}
                                  </span>
                                </div>
                                {s.net_payable <= 0 && <p style={{ margin: '3px 0 0', fontSize: '0.62rem', color: '#16a34a' }}>Mukkadam is in credit</p>}
                              </div>

                              <div style={{ background: '#f9fafb', borderRadius: '8px', padding: '10px 12px', fontSize: '0.74rem' }}>
                                <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📅 Weekly Payments</p>
                                {s.weekly_payments.length === 0 ? (
                                  <p style={{ color: '#9ca3af', fontSize: '0.7rem', margin: 0 }}>No weekly payments</p>
                                ) : (
                                  <>
                                    {s.weekly_payments.map((w: any, wi: number) => (
                                      <div key={wi} style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '4px', marginBottom: '4px', borderBottom: wi < s.weekly_payments.length - 1 ? '1px solid #e5e7eb' : 'none' }}>
                                        <div>
                                          <span style={{ fontWeight: 600 }}>{w.payment_date}</span>
                                          <span style={{ color: '#9ca3af', marginLeft: '5px', fontSize: '0.64rem' }}>{w.crew_size_on_date} workers</span>
                                        </div>
                                        <span style={{ fontWeight: 700, color: '#dc2626' }}>−₹{Number(w.amount).toLocaleString('en-IN')}</span>
                                      </div>
                                    ))}
                                    <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '4px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                                      <span>Total</span>
                                      <span style={{ color: '#dc2626' }}>
  −₹{s.weekly_payments.reduce((sum: number, w: any) => sum + w.amount, 0).toLocaleString('en-IN')}
</span></div>
                                  </>
                                )}
                              </div>
                            </div>
                            {/* Cross-job net summary — shown once per mukkadam after all settlement cards */}
{(() => {
  // Find which jobs had their credit absorbed into a later job
  const absorbedJobIds = new Set(
    m.settlements
      .filter((s: any) => s.credit_carried_forward > 0)
      .map((s: any) => s.job_id) // these jobs absorbed credit from previous
  );

  // The "real" remaining credit is only from jobs whose credit was NOT yet absorbed
  // i.e. the latest job in credit that no one else carried forward from
  const latestNet = m.settlements.reduce((sum: number, s: any) => sum + s.net_payable, 0);
  
  // Correct: sum only the jobs that haven't been absorbed
  // Job 1774 credit was absorbed into 1822, so only count 1822
  const alreadyAbsorbedCredit = m.settlements
    .filter((s: any) => s.net_payable < 0)
    .reduce((sum: number, s: any) => {
      // If another job carried forward credit from this job, don't count it again
      const wasAbsorbed = m.settlements.some(
        (other: any) => other.credit_carried_forward > 0 && other.job_id !== s.job_id
      );
      return wasAbsorbed ? sum + s.net_payable : sum; // net_payable is negative
    }, 0);

  const trueRemainingNet = latestNet - alreadyAbsorbedCredit;
  // = (-9223 + -7003) - (-7003) = -9223 ✓

  const toPayTotal = m.settlements
    .filter((s: any) => s.net_payable > 0)
    .reduce((sum: number, s: any) => sum + s.net_payable, 0);

  return (
    <div style={{ background: toPayTotal > 0 ? '#fef2f2' : '#f0fdf4', border: `1px solid ${toPayTotal > 0 ? '#fecaca' : '#bbf7d0'}`, borderRadius: 8, padding: '10px 14px', marginTop: 4 }}>
      <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📊 All Jobs Summary</p>

      {m.settlements.map((s: any) => {
        const wasAbsorbed = m.settlements.some(
          (other: any) => other.credit_carried_forward > 0 && other.job_id !== s.job_id
        );
        return (
          <div key={s.job_id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3, fontSize: '0.74rem' }}>
            <span style={{ color: '#6b7280' }}>
              Job #{s.job_id} ({s.farmer_name})
              {wasAbsorbed && s.net_payable < 0 && (
                <span style={{ fontSize: '0.6rem', color: '#9ca3af', marginLeft: 4 }}>(absorbed in next job)</span>
              )}
            </span>
            <span style={{ fontWeight: 700, color: s.net_payable > 0 ? '#dc2626' : '#16a34a' }}>
              {s.net_payable > 0
                ? `To Pay ₹${s.net_payable.toLocaleString('en-IN')}`
                : `In Credit ₹${Math.abs(s.net_payable).toLocaleString('en-IN')}`}
            </span>
          </div>
        );
      })}

      <div style={{ borderTop: '1.5px solid #e5e7eb', paddingTop: 5, display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
        <span>Net to Pay Mukkadam</span>
        <span style={{ fontSize: '0.92rem', color: toPayTotal > 0 ? '#dc2626' : '#16a34a' }}>
          {toPayTotal > 0
            ? `₹${toPayTotal.toLocaleString('en-IN')}`
            : `₹0 (in credit ₹${Math.abs(trueRemainingNet).toLocaleString('en-IN')})`}
        </span>
      </div>
    </div>
  );
})()}


                            <MiscCostsSection
                              mukkadamId={m.mukkadam_id}
                              jobId={s.job_id}
                              initialCosts={s.misc_costs || []}
                              onCostChange={fetchData}
                            />

                            {needsPay && (
                              <button
                                onClick={() => handleMukkadamPay(m.mukkadam_id, s.job_id, s.net_payable, m.mukkadam_name)}
                                disabled={mukkadamPaying === payKey}
                                style={{ width: '100%', marginTop: '10px', padding: '10px', borderRadius: '8px', border: 'none', background: mukkadamPaying === payKey ? '#99f6e4' : '#14b8a6', color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: mukkadamPaying === payKey ? 'not-allowed' : 'pointer' }}
                              >
                                {mukkadamPaying === payKey ? 'Processing...' : `🏦 Pay ₹${s.net_payable.toLocaleString('en-IN')} to ${m.mukkadam_name}`}
                              </button>
                            )}
                          </div>
                        );
                      })}
                      {/* Weekly Payment Button */}
{(() => {
  const assignment = m.assignment; // needs weekly_payment_day from backend
  if (assignment?.weekly_payment_day_value === null || assignment?.weekly_payment_day_value === undefined) return null;

  const today = new Date().getDay(); // 0=Sunday, 1=Monday...
  // JS: 0=Sun, 1=Mon... Python: 0=Mon, 6=Sun — convert
  const jsToday = today === 0 ? 6 : today - 1; // convert to Python weekday

  if (jsToday !== assignment.weekly_payment_day_value) return null;

  // Already paid today?
  const alreadyPaidToday = m.settlements
    .flatMap((s: any) => s.weekly_payments)
    .some((w: any) => w.payment_date === new Date().toISOString().split('T')[0]);

  if (alreadyPaidToday) return (
    <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '8px 12px', fontSize: '0.74rem', color: '#16a34a', fontWeight: 700 }}>
      ✓ Weekly payment already added today
    </div>
  );

  const amount = assignment.weekly_payment_amount;

  return (
    <div style={{ background: '#fefce8', border: '1px solid #fde68a', borderRadius: 8, padding: '10px 12px', marginBottom: 8 }}>
      <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#92400e', textTransform: 'uppercase' }}>📅 Weekly Payment Due Today</p>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>₹{Number(amount).toLocaleString('en-IN')}</span>
          <span style={{ color: '#6b7280', fontSize: '0.7rem', marginLeft: 6 }}>{m.crew_size} workers</span>
        </div>
        <button
          onClick={() => handleAddWeeklyPayment(m.mukkadam_id, assignment.assignment_id, amount)}
          style={{ background: '#d97706', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', fontWeight: 700, cursor: 'pointer', fontSize: '0.74rem' }}
        >
          + Add Payment
        </button>
      </div>
    </div>
  );
})()}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Farmer Payment Modal ── */}
      {payModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setPayModal(null)}>
          <div style={{ background: '#fff', borderRadius: '16px', padding: '24px', width: '360px', boxShadow: '0 24px 60px rgba(0,0,0,0.2)' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 700 }}>💰 Collect Payment</h3>
            <p style={{ margin: '0 0 18px', fontSize: '0.75rem', color: '#6b7280' }}>From {payModal.farmerName} · Job #{payModal.jobId}</p>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Amount (₹)</label>
            <input type="number" value={payAmount} onChange={e => setPayAmount(e.target.value)} style={{ width: '100%', padding: '10px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '1rem', fontWeight: 700, marginBottom: '10px', boxSizing: 'border-box' }} />
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Mode</label>
            <select value={payMode} onChange={e => setPayMode(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '10px', background: '#fff', boxSizing: 'border-box' }}>
              {['CASH', 'UPI', 'BANK_TRANSFER', 'CHEQUE', 'OTHER'].map(m => <option key={m} value={m}>{m}</option>)}
            </select>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Notes (optional)</label>
            <input value={payNotes} onChange={e => setPayNotes(e.target.value)} placeholder="e.g. Cash received" style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '18px', boxSizing: 'border-box' }} />
            <div style={{ display: 'flex', gap: '10px' }}>
              <button onClick={() => setPayModal(null)} style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.82rem', cursor: 'pointer' }}>Cancel</button>
              <button onClick={handleFarmerPay} disabled={payLoading} style={{ flex: 2, padding: '10px', borderRadius: '8px', border: 'none', background: payLoading ? '#93c5fd' : '#3b82f6', color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: payLoading ? 'not-allowed' : 'pointer' }}>
                {payLoading ? 'Recording...' : `Record ₹${parseFloat(payAmount || '0').toLocaleString('en-IN')}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
const FarmScheduler: React.FC<FarmSchedulerProps> = ({clusterId, onBackToClusters}) => {
  // State
  const [jobs, setJobs] = useState<Job[]>([]);
  const [mukkadams, setMukkadams] = useState<Mukkadam[]>([]);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
  const [loading, setLoading] = useState(false);
const [potentialByDate, setPotentialByDate] = useState<PotentialByDate>({});
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [selectedMukkadam, setSelectedMukkadam] = useState<Mukkadam | null>(null);

  // Modals
  const [showAllocationModal, setShowAllocationModal] = useState(false);
  const [showProductivityWarning, setShowProductivityWarning] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [pendingAllocation, setPendingAllocation] = useState<any>(null);
const [viewModes, setViewModes] = useState<('jobs' | 'allocations' | 'potential'| 'payments')[]>(['jobs']);

  // Load initial data
useEffect(() => {
  setJobs([]);      // ✅ clear stale data first
  setAllJobs([]);
  loadJobs(null);
  loadMukkadams();
  loadAllocations();
  loadLeaves();
  loadOverload();
  loadPotential();
}, [clusterId]);

const [leaves, setLeaves] = useState<any[]>([]);
// in parent, e.g. CalendarPage.tsx
const [selectedMukkadamCapacity, setSelectedMukkadamCapacity] = useState<number | null>(null);
const [overloadItems, setOverloadItems] = useState<any[]>([]);
type Filters = {
  farmerId: string | null;
  mukkadamId: number | null;
  cropName: string | null;
  variety: string | null;
  plotId: number | null;
  activityId: number | null;
  dateFrom: string | null; // "YYYY-MM-DD"
  dateTo: string | null;
};

const [filters, setFilters] = useState<Filters>({
  farmerId: null,
  mukkadamId: null,
  plotId: null,
  cropName: null,
  variety: null,
  activityId: null,
  dateFrom: null,
  dateTo: null,
});

const loadOverload = async () => {
  const res = await fetch(
    `${API_BASE_URL}/api/planning/by_activity_date/?cluster_id=${clusterId}`,
  );
  const data = await res.json();
  console.log('Loaded overload items:', data);
  setOverloadItems(data);
};
const loadPotential = async () => {
  const res = await fetch(
    `${API_BASE_URL}/api/clusters/${clusterId}/potential_jobs/`
  );
  const data = await res.json();
  console.log('Loaded potential jobs:', data);

  setPotentialByDate(data);
};
useEffect(() => {
  loadJobs();
  loadAllocations();
  loadLeaves();
  loadOverload();
  loadPotential();
}, [clusterId]);

const overloadMap: Record<string, any> = {};
overloadItems.forEach((o) => {
  const key = `${o.job_id}-${o.activity_id}-${o.scheduled_date}`;
  overloadMap[key] = o;
});


useEffect(() => {
  if (!selectedMukkadam || !selectedDate) {
    setSelectedMukkadamCapacity(null);
    return;
  }
  const dateStr = formatDate(selectedDate);   // ✅

  fetch(
    `${API_BASE_URL}/api/mukkadams/${selectedMukkadam.mukkadam_id}/daily_capacity/?date=${dateStr}&cluster_id=${clusterId}`,
  )
    .then((r) => r.json())
    .then((data) => setSelectedMukkadamCapacity(data.available_crew_size))
    .catch(() => setSelectedMukkadamCapacity(null));
}, [selectedMukkadam, selectedDate]);
const [dayCapacities, setDayCapacities] = useState<Record<string, number>>({});
// key: `${mukkadam_id}-${dateString}`, value: available_crew_size
useEffect(() => {
  const fetchDayCapacities = async () => {
    const dateStr = formatDate(selectedDate);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadams/daily_capacity_all/?date=${dateStr}&cluster_id=${clusterId}`,
      );
      const data = await res.json();
      const map: Record<string, number> = {};
      data.forEach((item: any) => {
        map[`${item.mukkadam_id}-${dateStr}`] = item.available_crew_size;
      });
      setDayCapacities(map);
    } catch (err) {
      console.error('Failed to load day capacities', err);
      setDayCapacities({});
    }
  };

  fetchDayCapacities();
}, [selectedDate]);

// load all mukkadams
const loadMukkadams = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/mukkadams/?cluster_id=${clusterId}`);
    const data = await response.json();

    const normalized = data.map((m: any) => ({
      ...m,
      mukkadam_id: m.mukkadam_id,
      crew_size: Number(m.crew_size) || 0,
    }));

    setMukkadams(normalized);
  } catch (error) {
    toast.error('Failed to load mukkadams');
    console.error(error);
  }
};


const [prefillData, setPrefillData] = useState<{
  jobId: string;
  activityId: number;
  activityDate?: string;
  farmerRate?: number;
  // team-click prefill
  mukkadamId?: number | null;
  allocatedArea?: number | null;
  allocatedWorkers?: number | null;
  mukkadamRate?: number | null;
} | null>(null);
const handleStartAllocationFromDay = (
  jobId: string,
  activityId: number,
  activity: any,
) => {
  const prefill = activity?.__prefill;

  if (prefill) {
    // ── Team click → direct allocation, no modal ──
    const allocationData = {
      job_id: jobId,
      job_activity_id: activityId,
      mukkadam_id: prefill.mukkadam_id,
      allocated_date: activity.scheduled_date,
      allocated_area: prefill.allocated_area,
      allocated_workers: prefill.allocated_workers,
      farmer_rate: activity.rate_per_acre,
      mukkadam_rate: prefill.mukkadam_rate,
      cluster_id: clusterId,
    };
    handleCreateAllocation([allocationData]);
    return;
  }

  // ── Regular Allocate → button → open modal ──
  setPrefillData({
    jobId,
    activityId,
    activityDate: activity.scheduled_date,
    farmerRate: activity.rate_per_acre,
  });
  setShowAllocationModal(true);
};



const handleAddDayCrew = async (mukkadam: Mukkadam, date: Date) => {
  const input = window.prompt(
    `Add extra workers for ${mukkadam.mukkadam_name} on ${formatDate(date)}:`,
    '0',
  );
  if (!input) return;
  const extra = parseInt(input, 10);
  if (Number.isNaN(extra) || extra <= 0) return;

  try {
    setLoading(true);
    await fetch(`${API_BASE_URL}/api/extra-workers/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mukkadam_id: mukkadam.mukkadam_id,
        mukkadam:mukkadam.mukkadam_id,
        date: formatDate(date),
        workers: extra,
      }),
    });
    await loadAllocations();
    await loadMukkadams();
  } finally {
    setLoading(false);
  }
};

const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);

useEffect(() => {
  if (!selectedMukkadam || !selectedDate) {
    setSelectedMukkadamCapacity(null);
    return;
  }
  const dateStr = formatDate(selectedDate);   // ✅

  fetch(
    `${API_BASE_URL}/api/mukkadams/${selectedMukkadam.mukkadam_id}/daily_capacity/?date=${dateStr}&cluster_id=${clusterId}`,
  )
    .then((r) => r.json())
    .then((data) => setSelectedMukkadamCapacity(data.available_crew_size))
    .catch(() => setSelectedMukkadamCapacity(null));
}, [selectedMukkadam, selectedDate]);

// helper for date formatting used in allocations filter

// 2. Add loadLeaves function
const loadLeaves = async () => {
  try {
    const startDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);
    const endDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0);
    
    const response = await fetch(
      `${API_BASE_URL}/api/leaves/?start_date=${formatDate(startDate)}&end_date=${formatDate(endDate)}&cluster_id=${clusterId}`
    );
    const data = await response.json();
    setLeaves(data);
  } catch (error) {
    console.error('Failed to load leaves');
  }
};

useEffect(() => {
  loadAllocations();
  loadLeaves();
}, [currentMonth]);


// FarmScheduler.tsx

// const [jobs, setJobs] = useState<Job[]>([]);
const [allJobs, setAllJobs] = useState<Job[]>([]); // ✅ Add this

const loadJobs = async (plotId?: number | null) => {
  const activePlotId = plotId !== undefined ? plotId : filters.plotId;
  
  console.log('loadJobs called, plotId:', activePlotId, 'filters.plotId:', filters.plotId);
  
  let url = `${API_BASE_URL}/api/jobs/?status=pending,scheduled,in_progress&cluster_id=${clusterId}`;
  if (activePlotId) {
    url += `&plot=${activePlotId}`;
  }
  
  console.log('Fetching URL:', url);  // ← check this in browser
  
  try {
    setLoading(true);
    const response = await fetch(url);
    const data = await response.json();
    setAllJobs(data);
    setJobs(data);
  } catch (error) {
    toast.error('Failed to load jobs');
  } finally {
    setLoading(false);
  }
};
// ✅ Jobs reload whenever clusterId OR plotId changes
useEffect(() => {
  loadJobs(filters.plotId);
}, [clusterId, filters.plotId]);

  const loadAllocations = async () => {
    try {
      const startDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);
      const endDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0);
      
      const response = await fetch(
        `${API_BASE_URL}/api/allocations/calendar_view/?start_date=${formatDate(startDate)}&end_date=${formatDate(endDate)}&cluster_id=${clusterId}`
      );
      const data = await response.json();
      
      // Convert object to array
      const allocationsList: Allocation[] = [];
      Object.values(data).forEach((dayAllocations: any) => {
        allocationsList.push(...dayAllocations);
      });
      
      setAllocations(allocationsList);
    } catch (error) {
      toast.error('Failed to load allocations');
      console.error(error);
    }
  };


  //   const [jobs, setJobs] = useState<Job[]>([]);
  // const [loading, setLoading] = useState(false);
  const [selectedFarmerId, setSelectedFarmerId] = useState<string | null>(null);
  const [selectedFarmerName, setSelectedFarmerName] = useState<string | null>(null);


  // const loadJobs = async () => {
  //   setLoading(true);
  //   try {
  //     const response = await fetch(`http://localhost:8001/tender/api/jobs/?cluster=${clusterId}`);
  //     const data = await response.json();
  //     setJobs(data);
  //   } catch (error) {
  //     console.error('Failed to load jobs:', error);
  //   } finally {
  //     setLoading(false);
  //   }
  // };

  const handleFarmerSelect = (farmerId: string, farmerName: string) => {
    setSelectedFarmerId(farmerId);
    setSelectedFarmerName(farmerName);
  };
const loadData = async () => {
  await loadMukkadams();
};
const inRange = (dateStr: string | null | undefined): boolean => {
  if (!dateStr) return true; // ignore if no date
  const d = dateStr;
  if (filters.dateFrom && d < filters.dateFrom) return false;
  if (filters.dateTo && d > filters.dateTo) return false;
  return true;
};

// allocationData is now an array of allocations from the modal
const handleCreateAllocation = async (allocationData: any[]) => {
  const isMultiTeam = allocationData.length > 1;
  
  // For STRICT activities with multiple teams, validate the total first
  if (isMultiTeam) {
    const job = jobs.find(j => j.job_id === allocationData[0].job_id);
    const activity = job?.activities?.find(a => a.id === allocationData[0].job_activity_id);
    
    if (activity?.is_strict) {
      // 👇 NEW: Check all dates are the same for STRICT
      const uniqueDates = new Set(allocationData.map(a => a.allocated_date));
      if (uniqueDates.size > 1) {
        toast.error(
          `STRICT activity must be allocated on ONE date. ` +
          `You selected: ${Array.from(uniqueDates).join(', ')}`
        );
        return;
      }
      
      // 👇 Check total area matches remaining
      const totalArea = allocationData.reduce((sum, alloc) => sum + alloc.allocated_area, 0);
      
      if (Math.abs(totalArea - activity.remaining_area) > 0.01) {
        toast.error(
          `Strict activity requires full allocation. ` +
          `Remaining: ${activity.remaining_area} acres, ` +
          `You're allocating: ${totalArea} acres`
        );
        return;
      }
    }
  }
  
  // Create all allocations
  for (const alloc of allocationData) {
    setPendingAllocation(alloc);
    await validateAllocation(alloc, isMultiTeam);
  }
};
const validateAllocation = async (allocationData: any, isMultiTeam: boolean = false) => {
  try {
    setLoading(true);

    // 1️⃣ Check leave availability
    const leaveCheckResponse = await fetch(
      `${API_BASE_URL}/api/leaves/check_availability/?date=${allocationData.allocated_date}&mukkadam_id=${allocationData.mukkadam_id}&cluster_id=${clusterId}`
    );

    const leaveCheck = await leaveCheckResponse.json();

    if (!leaveCheckResponse.ok) {
      toast.error(leaveCheck.message || "Leave check failed");
      return;
    }

    if (!leaveCheck.available) {
      toast.error(leaveCheck.message);
      return;
    }

    // 2️⃣ Validate allocation
    const job = jobs.find(j => j.job_id === allocationData.job_id);
    const activity = job?.activities?.find(a => a.id === allocationData.job_activity_id);
    const isActivityStrict = activity?.is_strict || false;
    
    // Skip strict check ONLY if multi-team AND strict (already validated in handleCreateAllocation)
    const skipStrictCheck = isMultiTeam && isActivityStrict;

    const response = await fetch(
      `${API_BASE_URL}/api/allocations/validate_allocation/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_activity_id: allocationData.job_activity_id,
          mukkadam_id: allocationData.mukkadam_id,
          allocated_date: allocationData.allocated_date,
          allocated_area: allocationData.allocated_area,
          allocated_workers: allocationData.allocated_workers,
          skip_strict_check: skipStrictCheck,
          cluster_id: clusterId,
        }),
      }
    );

    const result = await response.json();

    if (!response.ok) {
      toast.error(result.error || result.message || "Validation error");
      return;
    }

    setValidationResult(result);

    if (result.can_allocate) {
      if (result.warnings && Object.keys(result.warnings).length > 0) {
        toast.success("Validation passed with warnings");
      }
      await createAllocation(allocationData, false, skipStrictCheck);
    } else {
      setShowProductivityWarning(true);
    }
  } catch (error) {
    toast.error("Validation failed");
    console.error(error);
  } finally {
    setLoading(false);
  }
};
const createAllocation = async (allocationData: any, force: boolean = false, skipStrictCheck: boolean = false) => {  // 👈 Add parameter
  try {
    setLoading(true);
    const response = await fetch(`${API_BASE_URL}/api/allocations/create_allocation/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        ...allocationData, 
        force,
        skip_strict_check: skipStrictCheck,  // 👈 ADD THIS
        cluster_id: clusterId,
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      toast.success('Allocation created successfully!');
      setShowAllocationModal(false);
      setShowProductivityWarning(false);
      loadAllocations();
      loadJobs();
    } else {
      toast.error(result.error || 'Failed to create allocation');
    }
  } catch (error) {
    toast.error('Failed to create allocation');
    console.error(error);
  } finally {
    setLoading(false);
  }
};



  const handleSuggestionSelected = async (suggestion: any) => {
    switch (suggestion.option) {
      case 'reduce_area':
        setPendingAllocation({
          ...pendingAllocation,
          allocated_area: suggestion.allocation.area
        });
        await createAllocation({
          ...pendingAllocation,
          allocated_area: suggestion.allocation.area
        });
        break;
        
      case 'add_workers':
        setPendingAllocation({
          ...pendingAllocation,
          allocated_workers: suggestion.allocation.workers
        });
        await createAllocation({
          ...pendingAllocation,
          allocated_workers: suggestion.allocation.workers
        });
        break;
        
      case 'update_productivity':
        await updateProductivity(suggestion);
        await createAllocation(pendingAllocation);
        break;
        
      case 'split_days':
        await createSplitAllocations(suggestion.allocations);
        break;
    }
  };

  const updateProductivity = async (suggestion: any) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/mukkadam-rates/update_rate_and_productivity/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mukkadam_id: pendingAllocation.mukkadam_id,
          activity_id: pendingAllocation.activity_id,
          rate_per_acre: pendingAllocation.mukkadam_rate,
          productivity_per_worker: suggestion.allocation.new_productivity
        })
      });
      
      const result = await response.json();
      if (result.success) {
        toast.success('Productivity updated successfully');
      }
    } catch (error) {
      toast.error('Failed to update productivity');
      console.error(error);
    }
  };

  const createSplitAllocations = async (allocations: any[]) => {
    try {
      for (const alloc of allocations) {
        await createAllocation({
          ...pendingAllocation,
          allocated_area: alloc.area,
          allocated_date: alloc.date === 'next_day' 
            ? formatDate(new Date(new Date(pendingAllocation.allocated_date).getTime() + 86400000))
            : alloc.date
        });
      }
      toast.success('Split allocations created successfully!');
    } catch (error) {
      toast.error('Failed to create split allocations');
      console.error(error);
    }
  };

  const handleForceOverride = async () => {
    await createAllocation(pendingAllocation, true);
  };

const formatDate = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

// adjusted mukkadams list for the bottom panel
const adjustedMukkadams = mukkadams.map((m) => {
  const dateStr = formatDate(selectedDate);
  const key = `${m.mukkadam_id}-${dateStr}`;
  const dayCapacity = dayCapacities[key];

  return {
    ...m,
    available_crew_size:
      dayCapacity != null
        ? dayCapacity
        : m.crew_size, // fallback if API failed
  };
});



const filteredPotentialByDate: PotentialByDate = {};
Object.entries(potentialByDate).forEach(([dateStr, list]) => {
  if (!inRange(dateStr)) return;
  const kept = list.filter(p => {
    if (filters.farmerId && p.farmerId !== filters.farmerId) return false;
    if (filters.plotId && p.plotId !== filters.plotId) return false;
    if (filters.activityId && p.activityId !== filters.activityId) return false;
    if (filters.cropName && p.cropName !== filters.cropName) return false;
    if (filters.variety && p.variety !== filters.variety) return false;
    return true;
  });
  if (kept.length) filteredPotentialByDate[dateStr] = kept;
});
const filteredJobs = jobs.filter(job => {
  // farmer filter
  if (filters.farmerId && job.farmer_id !== filters.farmerId) return false;

  // plot filter
  if (filters.plotId && job.plot !== filters.plotId) return false;

  // CROP filter - NEW
  if (filters.cropName && job.crop_name !== filters.cropName) return false;

  // VARIETY filter - NEW
  if (filters.variety && job.variety !== filters.variety) return false;

  const acts = job.activities || [];

  // activity filter
  if (filters.activityId) {
    const hasAct = acts.some(a => a.activity_id === filters.activityId);
    if (!hasAct) return false;
  }

  // date range: at least one activity in range
  if (filters.dateFrom || filters.dateTo) {
    const hasInRange = acts.some(a => inRange(a.scheduled_date));
    if (!hasInRange) return false;
  }

  return true;
});
const jobsByDate: Record<string, Job[]> = {};

filteredJobs.forEach((job) => {
  (job.activities || []).forEach((act) => {
    if (!act.scheduled_date) return;
    
    // ✅ Apply activity filter here
    if (filters.activityId && act.activity_id !== filters.activityId) return;
    
    const key = act.scheduled_date;
    if (!jobsByDate[key]) jobsByDate[key] = [];
    
    // Clone job with only matching activities for this date
    const existingJob = jobsByDate[key].find(j => j.job_id === job.job_id);
    if (!existingJob) {
      jobsByDate[key].push({
        ...job,
        activities: job.activities?.filter(a => 
          a.scheduled_date === key &&
          (!filters.activityId || a.activity_id === filters.activityId)
        )
      });
    }
  });
});
const filteredAllocations = allocations.filter(a => {
  const job = jobs.find(j => j.job_id === a.job_id);
  if (!job) return false;

  if (filters.farmerId && job.farmer_id !== filters.farmerId) return false;
  if (filters.plotId && job.plot !== filters.plotId) return false;
  
  // CROP filter - NEW
  if (filters.cropName && job.crop_name !== filters.cropName) return false;
  
  // VARIETY filter - NEW
  if (filters.variety && job.variety !== filters.variety) return false;

  if (filters.activityId) {
    const acts = job.activities || [];
    if (!acts.some(act => act.activity_id === filters.activityId)) return false;
  }

  if (filters.mukkadamId && a.mukkadam !== filters.mukkadamId) return false;
  if ((filters.dateFrom || filters.dateTo) && !inRange(a.allocated_date)) return false;

  return true;
});

const handleRefreshAll = async () => {
  // clear filters/state if you want
  // setFilters({ farmerId: null, mukkadamId: null, plotId: null, activityId: null, dateFrom: null, dateTo: null });

  await Promise.all([
    loadJobs(),          // all jobs
    loadAllocations(),   // allocations
    loadMukkadams(),     // teams / workers
    loadLeaves(),        // leaves
    loadPotential(),
    loadOverload(),  // if you have this
       // if you have farmer/plot list
  ]);
};

const setViewMode = (mode: 'jobs' | 'allocations' | 'both' | 'payments') => {
  if (mode === 'both') {
    setViewModes(['jobs', 'allocations']);
  } else if (mode === 'payments') {
    setViewModes(['payments']);
  } else {
    setViewModes([mode]);
  }
};

const currentMode = viewModes.includes('payments')
  ? 'payments'
  : viewModes.includes('jobs') && viewModes.includes('allocations')
  ? 'both'
  : viewModes.includes('allocations')
  ? 'allocations'
  : 'jobs';
const toggleViewMode = (mode: 'jobs' | 'allocations' | 'potential') => {
  setViewModes(prev => {
    if (prev.includes(mode)) {
      // Remove if already selected (but keep at least one)
      return prev.length > 1 ? prev.filter(m => m !== mode) : prev;
    } else {
      // Add if not selected
      return [...prev, mode];
    }
  });
};


const filteredMukkadams = adjustedMukkadams.filter(m => {
  // mukkadam filter
  if (filters.mukkadamId && m.mukkadam_id !== filters.mukkadamId) return false;

  // date filter: show only those who have allocations in range OR crew_size>0 if only date filter
  if (filters.dateFrom || filters.dateTo || filters.farmerId) {
    const hasAlloc = filteredAllocations.some(
      a => a.mukkadam === m.mukkadam_id
    );
    return hasAlloc;
  }

  // only date filter case with no farmer/mukkadam: show crew_size > 0
  if (!filters.farmerId && !filters.mukkadamId && (filters.dateFrom || filters.dateTo)) {
    return m.available_crew_size > 0;
  }

  return true;
});
// unique plots from jobs (for plot filter)
const plotOptions = [
  ...new Map(
    jobs
      .filter(j => !filters.farmerId || j.farmer_id === filters.farmerId)
      .map(j => [j.plot, { id: j.plot, name: j.plot_name }])  // ❌ job.plot is the MAIN plot only
  ).values(),
].filter(p => p.id);
// unique activities from jobs (for activity filter)
const activityOptions = [
  ...new Map(
    jobs.flatMap(j =>
      (j.activities || []).map(a => [
        a.activity_id,
        { id: a.activity_id, name: a.activity_name },
      ]),
    ),
  ).values(),
];
// unique crops from jobs
const cropOptions = [
  ...new Set(
    jobs
      .filter(j => {
        // apply existing filters for dependent behavior
        if (filters.farmerId && j.farmer_id !== filters.farmerId) return false;
        if (filters.plotId && j.plot !== filters.plotId) return false;
        return true;
      })
      .map(j => j.crop_name)
      .filter(Boolean) // remove null/undefined
  )
].sort();

// unique varieties from jobs - filtered by selected crop if any
const varietyOptions = [
  ...new Set(
    jobs
      .filter(j => {
        // apply existing filters
        if (filters.farmerId && j.farmer_id !== filters.farmerId) return false;
        if (filters.plotId && j.plot !== filters.plotId) return false;
        if (filters.cropName && j.crop_name !== filters.cropName) return false;
        return true;
      })
      .map(j => j.variety)
      .filter(Boolean)
  )
].sort();

  return (
    <div className="farm-scheduler">
      <Toaster position="top-right" />
      
<header className="scheduler-header">
  {/* LEFT: back + title */}
  <div className="header-content">
    <button
      className="btn-secondary back-button"
      onClick={onBackToClusters}
    >
      ← Back to clusters
    </button>

    {/* <div>
      <h1>Farm Labor Scheduling System</h1>
      <div className="header-subtitle">
        Multi-Team · Smart Allocation · Real-time Capacity Tracking
      </div>
    </div> */}
  </div>

  {/* CENTER: filters + view tabs */}
  <div className="header-center">
<div className="filter-bar">
  {/* farmer */}
  <select
    value={filters.farmerId || ''}
    onChange={(e) =>
      setFilters(f => ({
        ...f,
        farmerId: e.target.value || null,
        plotId: null, // reset plot when farmer changes
      }))
    }
    className="form-select"
  >
    <option value="">All farmers</option>
    {[...new Map(
      jobs.map(j => [j.farmer_id, { id: j.farmer_id, name: j.farmer_name }])
    ).values()].map(f => (
      <option key={f.id} value={f.id}>{f.name}</option>
    ))}
  </select>

  {/* plot */}
  <select
    value={filters.plotId ?? ''}
    onChange={(e) =>
  setFilters(f => {
    console.log('Plot selected:', e.target.value);  // ✅ add this
    return {
      ...f,
      plotId: e.target.value ? Number(e.target.value) : null,
    };
  })
}
    className="form-select"
  >
    <option value="">All plots</option>
    {plotOptions.map(p => (
      <option key={p.id} value={p.id}>
        {p.name}
      </option>
    ))}
  </select>

  {/* CROP NAME - NEW */}
  <select
    value={filters.cropName || ''}
    onChange={(e) =>
      setFilters(f => ({
        ...f,
        cropName: e.target.value || null,
        variety: null, // reset variety when crop changes
      }))
    }
    className="form-select"
  >
    <option value="">All crops</option>
    {cropOptions.map(c => (
      <option key={c} value={c}>
        {c}
      </option>
    ))}
  </select>

  {/* VARIETY - NEW */}
  <select
    value={filters.variety || ''}
    onChange={(e) =>
      setFilters(f => ({
        ...f,
        variety: e.target.value || null,
      }))
    }
    className="form-select"
  >
    <option value="">All varieties</option>
    {varietyOptions.map(v => (
      <option key={v} value={v}>
        {v}
      </option>
    ))}
  </select>

  {/* activity */}
  <select
    value={filters.activityId ?? ''}
    onChange={(e) =>
      setFilters(f => ({
        ...f,
        activityId: e.target.value ? Number(e.target.value) : null,
      }))
    }
    className="form-select"
  >
    <option value="">All activities</option>
    {activityOptions.map(a => (
      <option key={a.id} value={a.id}>
        {a.name}
      </option>
    ))}
  </select>

  {/* mukkadam */}
  <select
    value={filters.mukkadamId ?? ''}
    onChange={(e) =>
      setFilters(f => ({
        ...f,
        mukkadamId: e.target.value ? Number(e.target.value) : null,
      }))
    }
    className="form-select"
  >
    <option value="">All teams</option>
    {mukkadams.map(m => (
      <option key={m.mukkadam_id} value={m.mukkadam_id}>
        {m.mukkadam_name}
      </option>
    ))}
  </select>

  {/* dates */}
  <input
    type="date"
    value={filters.dateFrom || ''}
    onChange={(e) =>
      setFilters(f => ({ ...f, dateFrom: e.target.value || null }))
    }
    className="form-input"
  />
  <span>to</span>
  <input
    type="date"
    value={filters.dateTo || ''}
    onChange={(e) =>
      setFilters(f => ({ ...f, dateTo: e.target.value || null }))
    }
    className="form-input"
  />

  <button
    className="btn-secondary"
    onClick={() =>
      setFilters({
        farmerId: null,
        mukkadamId: null,
        plotId: null,
        activityId: null,
        cropName: null,
        variety: null,
        dateFrom: null,
        dateTo: null,
      })
    }
  >
    Clear
  </button>
</div>

<div className="view-tabs">
  <button className={currentMode === 'jobs' ? 'tab active' : 'tab'} onClick={() => setViewMode('jobs')}>AI</button>
  <button className={currentMode === 'allocations' ? 'tab active' : 'tab'} onClick={() => setViewMode('allocations')}>Allocations</button>
  <button className={currentMode === 'both' ? 'tab active' : 'tab'} onClick={() => setViewMode('both')}>Both</button>
  {/* <button className={currentMode === 'payments' ? 'tab active' : 'tab'} onClick={() => setViewMode('payments')}>
    💰 Payments
  </button> */}
</div>
  </div>

  {/* RIGHT: actions */}
  <div className="header-actions">
    {/* <button
      className="btn-primary"
      onClick={() => setShowAllocationModal(true)}
    >
      + Create Allocation
    </button> */}
    {/* <button className="btn-secondary" onClick={handleRefreshAll}>
      🔄 Refresh
    </button> */}
  </div>
</header>




      {/* Main Layout */}
<div className="scheduler-layout">
  <div className="panel-left-content">
    
    <JobsPanel
      jobs={jobs}
          loading={loading}
          onRefresh={loadJobs}
          onFarmerSelect={handleFarmerSelect}
          clusterId={clusterId}
    />


  {/* <div className="job-details-wrapper">
    <JobDetailPanel
    selectedFarmerId={selectedFarmerId}
          selectedFarmerName={selectedFarmerName}
          onActivityAdded={loadJobs}
          clusterId={clusterId}
    />
  </div> */}
</div>




        {/* Center Panel - Calendar */}
        <div className="center-panel">
{

currentMode === 'payments' ? (
    <PaymentDashboard clusterId={clusterId} />
  ) 
  
  
  : (

<CalendarPanel
  currentMonth={currentMonth}
  selectedDate={selectedDate}
  jobs={filteredJobs}  
  allJobs={jobs}     
  allocations={filteredAllocations}
  mukkadams={adjustedMukkadams}   // ✅ use adjusted, not mukkadams
  leaves={leaves}
  jobsByDate={jobsByDate}
  viewModes={viewModes}
  filters={filters}
  setFilters={setFilters}
  // setViewMode={setViewMode}
  onMonthChange={setCurrentMonth}
  onDateSelect={setSelectedDate}
  onAllocationClick={(allocation) => console.log('Allocation clicked:', allocation)}
  onLeavesUpdated={loadLeaves}
  clusterId={clusterId}
  overloadMap={overloadMap}
  potentialByDate={filteredPotentialByDate}
  onStartAllocation={handleStartAllocationFromDay}  
/>
  )}


        </div>

        {/* Right Panel - Mukkadams */}
{/* <div className="panel right-panel">
  <div className="right-split">
    <div className="right-top">
      <MukkadamDetailPanel
        mukkadam={
          selectedMukkadam
            ? {
                ...selectedMukkadam,
                available_crew_size:
                  selectedMukkadamCapacity ?? selectedMukkadam.crew_size,
              }
            : null
        }
        onRefresh={loadData}
      />
    </div>

    <div className="right-bottom">
      <MukkadamPanel
        mukkadams={filteredMukkadams}
        selectedDate={selectedDate}
        allocations={allocations.filter(
          (a) =>
            formatDate(new Date(a.allocated_date)) === formatDate(selectedDate),
        )}
        loading={loading}
        onRefresh={loadMukkadams}
        onAddDayCrew={handleAddDayCrew} 
        onMukkadamClick={(m) => setSelectedMukkadam(m)}
        clusterId={clusterId}  
      />
    </div>
  </div>
</div> */}



      </div>
      

      {/* Modals */}
      {showAllocationModal && (
        <AllocationModal
          jobs={jobs}
    mukkadams={mukkadams}
    selectedDate={selectedDate}
    clusterId={clusterId}
    onCreate={handleCreateAllocation}
    initialJobId={prefillData?.jobId}
    initialActivityId={prefillData?.activityId}
    initialDate={prefillData?.activityDate}
    initialFarmerRate={prefillData?.farmerRate}
    onClose={() => {
      setShowAllocationModal(false);
      setPrefillData(null);
    }}
        />
      )}

      {showProductivityWarning && validationResult && (
        <ProductivityWarningModal
          validation={validationResult}
          pendingAllocation={pendingAllocation}
          onClose={() => setShowProductivityWarning(false)}
          onSuggestionSelect={handleSuggestionSelected}
          onForceOverride={handleForceOverride}
        />
      )}
    </div>
  );
};

export default FarmScheduler;