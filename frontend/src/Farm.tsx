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
import Dialpad from './call';
import { getFileExtension, uploadFileToS3 } from './utils/s3';
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
// // ─── Misc Costs Section ───────────────────────────────────

interface FarmSchedulerProps {clusterId: number;onBackToClusters: () => void;
  onOpenDialpadWithNumber: (phone: string) => void;}
function PaymentDashboard({ clusterId }: { clusterId: number }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'farmers' | 'mukkadams'>('farmers');
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [expandedAlloc, setExpandedAlloc] = useState<number | null>(null);

  // Farmer payment modal
  const [payModal, setPayModal] = useState<{
    farmerId: string; jobId: string;
    amount: number; farmerName: string;
    existingPayments?: any[];
  } | null>(null);
  const [payAmount, setPayAmount] = useState('');
  const [payMode, setPayMode] = useState('CASH');
  const [payNotes, setPayNotes] = useState('');
  const [payLoading, setPayLoading] = useState(false);
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [proofUploading, setProofUploading] = useState(false);

  // Mukkadam pay loading
  const [mukkadamPaying, setMukkadamPaying] = useState<string | null>(null);

  // Mukkadam payment modal (settlement pay)
  const [mukkadamPayModal, setMukkadamPayModal] = useState<{
    mukkadamId: number; jobId: string; amount: number; name: string;
  } | null>(null);
  const [mukkadamPayMode, setMukkadamPayMode] = useState('CASH');
  const [mukkadamPayNotes, setMukkadamPayNotes] = useState('');
  const [mukkadamProofFile, setMukkadamProofFile] = useState<File | null>(null);
  const [mukkadamProofUploading, setMukkadamProofUploading] = useState(false);
  const [mukkadamPayLoading, setMukkadamPayLoading] = useState(false);

  // Weekly payment modal
const [weeklyModal, setWeeklyModal] = useState<{
  mukkadamId: number; assignmentId: number; amount: number; name: string;
  paymentDate?: string;  // ← ADD THIS
} | null>(null);

  const [weeklyMode, setWeeklyMode] = useState('CASH');
  const [weeklyNotes, setWeeklyNotes] = useState('');
  const [weeklyProofFile, setWeeklyProofFile] = useState<File | null>(null);
  const [weeklyProofUploading, setWeeklyProofUploading] = useState(false);
  const [weeklyPayLoading, setWeeklyPayLoading] = useState(false);

  // Farmer verify loading
  const [verifyLoading, setVerifyLoading] = useState<number | null>(null);

  // Dispute override state
  const [disputeOpen, setDisputeOpen] = useState<number | null>(null);
  const [disputeArea, setDisputeArea] = useState('');
  const [disputeReason, setDisputeReason] = useState('');
  const [disputeSaving, setDisputeSaving] = useState(false);

  // OTP resend + verify state
  const [otpSending, setOtpSending] = useState<number | null>(null);
  const [otpOpen, setOtpOpen] = useState<number | null>(null);
  const [otpCode, setOtpCode] = useState('');
  const [otpVerifying, setOtpVerifying] = useState(false);

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
    if (!proofFile) { alert('Please attach payment proof before recording'); return; }
    setProofUploading(true);
    let proofS3Key: string | null = null;
    try {
      // Use existing S3 upload util — same as rest of the app
      // const { uploadFileToS3, getFileExtension } = await import('../utils/s3Upload');
      const userToken = localStorage.getItem('authToken') || localStorage.getItem('token') || '';
      const ext = getFileExtension(proofFile);
      const s3Name = `payments/farmer/${payModal.farmerId}/job_${payModal.jobId}_${Date.now()}.${ext}`;
      proofS3Key = await uploadFileToS3(proofFile, s3Name, userToken);
      if (!proofS3Key) { alert('❌ Proof upload failed. Please try again.'); return; }
    } catch(e) {
      alert('❌ Proof upload error'); return;
    } finally {
      setProofUploading(false);
    }

    setPayLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/farmer/${payModal.farmerId}/job/${payModal.jobId}/payment/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            amount: parseFloat(payAmount),
            mode: payMode,
            notes: payNotes,
            proof_s3_key: proofS3Key,
          }),
        }
      );
      const result = await res.json();
      if (res.ok) {
        alert(`✅ ${result.message}`);
        setPayModal(null); setProofFile(null);
        fetchData();
        
      } else {
        alert(`❌ ${result.error}`);
      }
    } finally {
      setPayLoading(false);
    }
  };

  const handleMukkadamPay = (mukkadamId: number, jobId: string, amount: number, name: string) => {
    setMukkadamPayModal({ mukkadamId, jobId, amount, name });
    setMukkadamPayMode('CASH'); setMukkadamPayNotes(''); setMukkadamProofFile(null);
  };

  const submitMukkadamPay = async () => {
    if (!mukkadamPayModal || !mukkadamProofFile) return;
    setMukkadamProofUploading(true);
    let proofS3Key: string | null = null;
    try {
      // const { uploadFileToS3, getFileExtension } = await import('../utils/s3Upload');
      const userToken = localStorage.getItem('authToken') || localStorage.getItem('token') || '';
      const ext = getFileExtension(mukkadamProofFile);
      const s3Name = `payments/mukkadam/${mukkadamPayModal.mukkadamId}/job_${mukkadamPayModal.jobId}_${Date.now()}.${ext}`;
      proofS3Key = await uploadFileToS3(mukkadamProofFile, s3Name, userToken);
      if (!proofS3Key) { alert('❌ Proof upload failed'); return; }
    } finally { setMukkadamProofUploading(false); }

    setMukkadamPayLoading(true);
    const key = `${mukkadamPayModal.mukkadamId}-${mukkadamPayModal.jobId}`;
    setMukkadamPaying(key);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamPayModal.mukkadamId}/settlement/${mukkadamPayModal.jobId}/pay/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: mukkadamPayMode, notes: mukkadamPayNotes, proof_s3_key: proofS3Key }),
        }
      );
      const result = await res.json();
      if (res.ok) {
        alert(`✅ ${result.message}`);
        setMukkadamPayModal(null); setMukkadamProofFile(null);
        fetchData();
      } else { alert(`❌ ${result.error}`); }
    } finally { setMukkadamPayLoading(false); setMukkadamPaying(null); }
  };

  const handleAddWeeklyPayment = (mukkadamId: number, assignmentId: number, amount: number, name: string) => {
    setWeeklyModal({ mukkadamId, assignmentId, amount, name });
    setWeeklyMode('CASH'); setWeeklyNotes(''); setWeeklyProofFile(null);
  };

  const submitWeeklyPayment = async () => {
    if (!weeklyModal || !weeklyProofFile) return;
    setWeeklyProofUploading(true);
    let proofS3Key: string | null = null;
    try {
      // const { uploadFileToS3, getFileExtension } = await import('../utils/s3Upload');
      const userToken = localStorage.getItem('authToken') || localStorage.getItem('token') || '';
      const ext = getFileExtension(weeklyProofFile);
      const s3Name = `payments/weekly/${weeklyModal.mukkadamId}/assignment_${weeklyModal.assignmentId}_${Date.now()}.${ext}`;
      proofS3Key = await uploadFileToS3(weeklyProofFile, s3Name, userToken);
      if (!proofS3Key) { alert('❌ Proof upload failed'); return; }
    } finally { setWeeklyProofUploading(false); }

    setWeeklyPayLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/weekly-payment/add/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
  assignment_id: weeklyModal.assignmentId,
  amount: weeklyModal.amount,
  payment_date: weeklyModal.paymentDate || new Date().toISOString().split('T')[0], // ← use missed date
  mode: weeklyMode,
  notes: weeklyNotes ? `${weeklyNotes} (late — was due ${weeklyModal.paymentDate})` : `Late payment — was due ${weeklyModal.paymentDate}`,
  proof_s3_key: proofS3Key,
}),
      });
      if (res.ok) {
        setWeeklyModal(null); setWeeklyProofFile(null);
        fetchData();
      } else {
        const d = await res.json();
        alert(`❌ ${d.error || 'Failed'}`);
      }
    } finally { setWeeklyPayLoading(false); }
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

  const handleResolveDispute = async (allocationId: number) => {
    if (!disputeArea) return;
    setDisputeSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/attendance/resolve-dispute/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          allocation_id: allocationId,
          farmer_claimed_area: parseFloat(disputeArea),
          dispute_reason: disputeReason,
        }),
      });
      const result = await res.json();
      if (res.ok) {
        setDisputeOpen(null);
        setDisputeArea('');
        setDisputeReason('');
        fetchData();
      } else {
        alert(`❌ ${result.error}`);
      }
    } finally {
      setDisputeSaving(false);
    }
  };

  const handleSendOtp = async (allocationId: number) => {
    setOtpSending(allocationId);
    try {
      const res = await fetch(`${API_BASE_URL}/api/attendance/send-farmer-otp/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allocation_id: allocationId }),
      });
      const result = await res.json();
      if (res.ok) {
        alert('✅ OTP sent to farmer');
        setOtpOpen(allocationId);
        setOtpCode('');
      } else {
        alert(`❌ ${result.error}`);
      }
    } finally {
      setOtpSending(null);
    }
  };

  const handleVerifyOtp = async (allocationId: number, farmerId: string) => {
    if (!otpCode.trim()) return;
    setOtpVerifying(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/attendance/verify-farmer-otp/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allocation_id: allocationId, otp: otpCode.trim(), farmer_id: farmerId }),
      });
      const result = await res.json();
      if (res.ok) {
        alert('✅ Farmer verified successfully');
        setOtpOpen(null);
        setOtpCode('');
        fetchData();
      } else {
        alert(`❌ ${result.error || 'Invalid OTP'}`);
      }
    } finally {
      setOtpVerifying(false);
    }
  };
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px', color: '#9ca3af' }}>
      <RefreshCw size={24} className="animate-spin" style={{ color: '#14b8a6', marginRight: '10px' }} />
      Loading payment data...
    </div>
  // );

  if (!data) return null;

  const STATUS_META: Record<string, { bg: string; text: string; label: string }> = {
    paid:              { bg: '#dcfce7', text: '#16a34a', label: '✓ Paid' },
    calculated:        { bg: '#fef9c3', text: '#b45309', label: '⚠ Due' },
    no_payment_needed: { bg: '#dbeafe', text: '#1d4ed8', label: '✅ Credit' },
    payment_raised:    { bg: '#fce7f3', text: '#be185d', label: 'Raised' },
    pending:           { bg: '#f3f4f6', text: '#6b7280', label: 'Pending' },
  };

  // ── Work + Payment status badges (BI team naming) ──────────────────────
  const WorkStatusBadge = ({ status }: { status: string }) => {
    const map: Record<string, { bg: string; color: string; label: string }> = {
      work_not_started: { bg: '#f3f4f6', color: '#6b7280',  label: 'Work Not Started' },
      in_progress:      { bg: '#dbeafe', color: '#1d4ed8',  label: 'In Progress' },
      completed:        { bg: '#dcfce7', color: '#16a34a',  label: 'Completed' },
    };
    const m = map[status] || map.work_not_started;
    return (
      <span style={{ fontSize: '0.58rem', padding: '2px 7px', borderRadius: '999px', fontWeight: 700, background: m.bg, color: m.color }}>
        {m.label}
      </span>
    );
  };

  const PaymentStatusBadge = ({ status }: { status: string }) => {
    const map: Record<string, { bg: string; color: string; label: string }> = {
      pending:  { bg: '#f3f4f6', color: '#6b7280',  label: 'Payment Pending' },
      dispute:  { bg: '#fef2f2', color: '#dc2626',  label: '🚨 Dispute' },
      done:     { bg: '#dcfce7', color: '#16a34a',  label: '✓ Done' },
      settled:  { bg: '#ede9fe', color: '#7c3aed',  label: 'Settled' },
    };
    const m = map[status] || map.pending;
    return (
      <span style={{ fontSize: '0.58rem', padding: '2px 7px', borderRadius: '999px', fontWeight: 700, background: m.bg, color: m.color }}>
        {m.label}
      </span>
    );
  };

  // ── Farmer verify status badge ──────────────────────────
  const VerifyBadge = ({ status }: { status: string }) => {
    const map: Record<string, { bg: string; color: string; label: string }> = {
      not_submitted:         { bg: '#f3f4f6', color: '#6b7280',  label: '⏳ Not Submitted' },
      pending_your_response: { bg: '#fef9c3', color: '#b45309',  label: '👀 Awaiting Your Response' },
      agreed:                { bg: '#dcfce7', color: '#16a34a',  label: '✅ You Agreed' },
      disputed:              { bg: '#fef2f2', color: '#dc2626',  label: '❌ Disputed' },
    };
    const m = map[status] || map.not_submitted;
    return (
      <span style={{ fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: m.bg, color: m.color }}>
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

    const workStatus = act.work_status || 'work_not_started';
    const paymentStatus = act.payment_status || 'pending';
    const isDispute = paymentStatus === 'dispute';
    const billingLocked = isDispute && !act.use_actual_for_settlement && !act.admin_override_area;
    const mukkadamClaimed = act.mukkadam_claimed_area ?? act.actual_area_done;
    // Farmer column: OTP verified = same as mukkadam. Team override = override area. Otherwise nothing.
    const farmerArea = act.admin_override_area != null
      ? act.admin_override_area
      : (act.farmer_agreed === true && mukkadamClaimed != null)
        ? mukkadamClaimed
        : null;
    const billingArea = act.admin_override_area ?? act.actual_area_done ?? act.allocated_area;

    return (
      <div style={{
        border: `1px solid ${isDispute ? '#fecaca' : verifyStatus === 'pending_your_response' ? '#fde68a' : verifyStatus === 'agreed' ? '#bbf7d0' : '#e5e7eb'}`,
        borderRadius: '8px', overflow: 'hidden', background: '#fff',
        marginBottom: '6px',
      }}>
        {/* Row header */}
        <div
          onClick={() => setExpandedAlloc(isExpanded ? null : act.allocation_id)}
          style={{
            display: 'grid',
            gridTemplateColumns: '2fr 0.8fr 1fr 1fr 1fr auto',
            gap: '8px', padding: '8px 12px',
            cursor: 'pointer', alignItems: 'center',
            fontSize: '0.74rem',
          }}
        >
          {/* Activity name + status badges */}
          <div>
            <p style={{ margin: 0, fontWeight: 700, color: '#111827' }}>{act.activity_name}</p>
            <p style={{ margin: 0, fontSize: '0.62rem', color: '#9ca3af' }}>{act.plot_code || act.plot_name || '—'}</p>
            <div style={{ display: 'flex', gap: '4px', marginTop: '3px', flexWrap: 'wrap' }}>
              <WorkStatusBadge status={workStatus} />
              <PaymentStatusBadge status={paymentStatus} />
              {act.is_carry_forward && (
                <span style={{ fontSize: '0.58rem', padding: '2px 7px', borderRadius: '999px', fontWeight: 700, background: '#fef9c3', color: '#b45309' }}>↩ Carry Fwd</span>
              )}
            </div>
          </div>

          {/* DATE */}
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0, fontWeight: 700, color: '#374151', fontSize: '0.72rem' }}>
              {act.allocated_date ? act.allocated_date.slice(5) : '—'}
            </p>
            <p style={{ margin: 0, fontSize: '0.58rem', color: '#9ca3af' }}>{act.allocated_workers}w</p>
          </div>

          {/* BI ASSIGNED */}
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0, fontWeight: 700, color: '#374151' }}>{Number(act.allocated_area).toFixed(2)} ac</p>
            <p style={{ margin: 0, fontSize: '0.58rem', color: '#9ca3af' }}>₹{Number(Number(act.allocated_area) * Number(act.rate_per_acre || 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
          </div>

          {/* MUKKADAM */}
          <div style={{ textAlign: 'center' }}>
            {mukkadamClaimed != null ? (
              <>
                <p style={{ margin: 0, fontWeight: 700, color: '#1d4ed8' }}>{Number(mukkadamClaimed).toFixed(2)} ac</p>
                <p style={{ margin: 0, fontSize: '0.58rem', color: '#9ca3af' }}>₹{Number(Number(mukkadamClaimed) * Number(act.mukkadam_rate || 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
              </>
            ) : (
              <p style={{ margin: 0, color: '#d1d5db', fontSize: '0.7rem' }}>—</p>
            )}
          </div>

          {/* FARMER */}
          <div style={{ textAlign: 'center' }}>
            {farmerArea != null ? (
              <>
                <p style={{ margin: 0, fontWeight: 700, color: act.admin_override_area != null ? '#d97706' : '#16a34a' }}>
                  {Number(farmerArea).toFixed(2)} ac
                </p>
                <p style={{ margin: 0, fontSize: '0.58rem', color: '#9ca3af' }}>₹{Number(Number(farmerArea) * Number(act.rate_per_acre || 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
              </>
            ) : isDispute ? (
              <p style={{ margin: 0, color: '#dc2626', fontSize: '0.62rem', fontWeight: 700 }}>🚨 Disputed</p>
            ) : verifyStatus === 'pending_your_response' ? (
              <p style={{ margin: 0, color: '#b45309', fontSize: '0.62rem', fontWeight: 600 }}>⏳ Pending</p>
            ) : (
              <p style={{ margin: 0, color: '#d1d5db', fontSize: '0.7rem' }}>—</p>
            )}
          </div>

          <span style={{ color: '#9ca3af', fontSize: '0.65rem' }}>{isExpanded ? '▲' : '▼'}</span>
        </div>

        {/* Dispute override panel — shown inline without expanding */}
        {isDispute && billingLocked && (
          <div style={{ borderTop: '1px solid #fecaca', background: '#fff5f5', padding: '10px 12px' }}>
            <p style={{ margin: '0 0 6px', fontSize: '0.68rem', fontWeight: 700, color: '#dc2626' }}>
              🚨 Dispute — Billing locked. Fill farmer's claim after call to unlock.
            </p>
            <div style={{ fontSize: '0.7rem', color: '#6b7280', marginBottom: '6px' }}>
              Mukkadam claimed: <strong style={{ color: '#1d4ed8' }}>{mukkadamClaimed != null ? `${Number(mukkadamClaimed).toFixed(2)} ac` : '—'}</strong>
            </div>
            {disputeOpen === act.allocation_id ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <input
                  type="number"
                  value={disputeArea}
                  onChange={e => setDisputeArea(e.target.value)}
                  placeholder="Farmer says (acres)"
                  style={{ width: '100%', padding: '6px 10px', border: '1px solid #fca5a5', borderRadius: '6px', fontSize: '0.78rem', boxSizing: 'border-box' }}
                />
                <textarea
                  value={disputeReason}
                  onChange={e => setDisputeReason(e.target.value)}
                  placeholder="Reason (water logging, crop damage...)"
                  rows={2}
                  style={{ width: '100%', padding: '6px 10px', border: '1px solid #fca5a5', borderRadius: '6px', fontSize: '0.72rem', resize: 'none', boxSizing: 'border-box' }}
                />
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    onClick={() => { setDisputeOpen(null); setDisputeArea(''); setDisputeReason(''); }}
                    style={{ flex: 1, padding: '6px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.72rem', cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleResolveDispute(act.allocation_id)}
                    disabled={disputeSaving || !disputeArea}
                    style={{ flex: 2, padding: '6px', borderRadius: '6px', border: 'none', background: disputeSaving ? '#fca5a5' : '#dc2626', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}
                  >
                    {disputeSaving ? 'Saving...' : 'Unlock Billing with This Area'}
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setDisputeOpen(act.allocation_id)}
                style={{ padding: '5px 12px', borderRadius: '6px', border: '1px solid #fca5a5', background: '#fff', color: '#dc2626', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer' }}
              >
                + Enter Farmer's Claim
              </button>
            )}
          </div>
        )}

        {/* Override applied indicator */}
        {isDispute && !billingLocked && act.admin_override_area != null && (
          <div style={{ borderTop: '1px solid #fed7aa', background: '#fff7ed', padding: '6px 12px', fontSize: '0.68rem', color: '#c2410c' }}>
            ⚠ Billing uses override area ({Number(act.admin_override_area).toFixed(2)} ac) — {act.dispute_reason}
          </div>
        )}

        {/* Expanded detail */}
        {isExpanded && (
          <div style={{ borderTop: '1px solid #f3f4f6', padding: '12px', background: '#fafafa' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '10px' }}>

              {/* Planned box */}
              <div style={{ background: '#eff6ff', borderRadius: '8px', padding: '10px 12px', fontSize: '0.72rem' }}>
                <p style={{ margin: '0 0 6px', fontSize: '0.62rem', fontWeight: 700, color: '#1d4ed8', textTransform: 'uppercase' }}>📋 Planned</p>
                {[
                  { label: 'Date',    val: act.allocated_date },
                  { label: 'Area',    val: `${Number(act.allocated_area).toFixed(2)} ac` },
                  { label: 'Workers', val: act.allocated_workers },
                  { label: 'Rate',    val: `₹${Number(act.mukkadam_rate).toLocaleString('en-IN')}/ac` },
                  { label: 'Amount',  val: `₹${Number(act.mukkadam_amount).toLocaleString('en-IN')}` },
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
                      { label: 'Claimed Area', val: `${Number(mukkadamClaimed).toFixed(2)} ac` },
                      { label: 'Crew Showed',  val: act.actual_crew_size },
                      { label: 'Start Time',   val: act.actual_start_time ? new Date(act.actual_start_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—' },
                      { label: 'End Time',     val: act.actual_end_time ? new Date(act.actual_end_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—' },
                      { label: 'Submitted',    val: act.report_submitted_at ? new Date(act.report_submitted_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : '—' },
                    ].map((r, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                        <span style={{ color: '#6b7280' }}>{r.label}</span>
                        <span style={{ fontWeight: 600, color: '#111827' }}>{r.val}</span>
                      </div>
                    ))}
                    {mukkadamClaimed && (
                      <div style={{ borderTop: '1px solid #bbf7d0', marginTop: '5px', paddingTop: '5px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                        <span style={{ color: '#6b7280' }}>Claimed Amt</span>
                        <span style={{ color: '#0f766e' }}>
                          ₹{(Number(mukkadamClaimed) * Number(act.mukkadam_rate)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
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
                      Mukkadam claimed <strong>{Number(mukkadamClaimed).toFixed(2)} ac</strong> done.
                      {areaDiffNum !== 0 && (
                        <span style={{ color: areaDiffNum < 0 ? '#dc2626' : '#0f766e', marginLeft: '4px' }}>
                          ({areaDiffNum > 0 ? '+' : ''}{areaDiff} vs planned)
                        </span>
                      )}
                    </p>
                    <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
                      <button
                        onClick={() => handleFarmerVerify(act.allocation_id, farmerId, act.job_id, true)}
                        disabled={verifyLoading === act.allocation_id}
                        style={{ flex: 1, padding: '6px', borderRadius: '6px', border: 'none', background: '#16a34a', color: '#fff', fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer' }}
                      >
                        {verifyLoading === act.allocation_id ? '...' : '✅ Agree'}
                      </button>
                      <button
                        onClick={() => handleFarmerVerify(act.allocation_id, farmerId, act.job_id, false)}
                        disabled={verifyLoading === act.allocation_id}
                        style={{ flex: 1, padding: '6px', borderRadius: '6px', border: 'none', background: '#dc2626', color: '#fff', fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer' }}
                      >
                        {verifyLoading === act.allocation_id ? '...' : '❌ Dispute'}
                      </button>
                    </div>
                    {/* OTP resend */}
                    <div style={{ borderTop: '1px solid #fde68a', paddingTop: '8px' }}>
                      <p style={{ margin: '0 0 6px', fontSize: '0.62rem', color: '#6b7280', fontWeight: 600 }}>VERIFY VIA OTP</p>
                      {otpOpen === act.allocation_id ? (
                        <div style={{ display: 'flex', gap: '5px' }}>
                          <input
                            type="text"
                            inputMode="numeric"
                            value={otpCode}
                            onChange={e => setOtpCode(e.target.value)}
                            placeholder="Enter OTP"
                            maxLength={6}
                            style={{ flex: 1, padding: '6px 10px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '0.9rem', fontWeight: 700, letterSpacing: '0.15em', textAlign: 'center' }}
                          />
                          <button
                            onClick={() => handleVerifyOtp(act.allocation_id, farmerId)}
                            disabled={otpVerifying || !otpCode.trim()}
                            style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: otpVerifying ? '#99f6e4' : '#14b8a6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
                          >
                            {otpVerifying ? '...' : '✓ Verify'}
                          </button>
                          <button onClick={() => { setOtpOpen(null); setOtpCode(''); }}
                            style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.72rem', cursor: 'pointer' }}>✕</button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleSendOtp(act.allocation_id)}
                          disabled={otpSending === act.allocation_id}
                          style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', color: '#374151', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer' }}
                        >
                          {otpSending === act.allocation_id ? 'Sending...' : '📱 Send OTP to Farmer'}
                        </button>
                      )}
                    </div>
                  </>
                )}

                {verifyStatus === 'agreed' && (
                  <>
                    <p style={{ margin: '0 0 4px', color: '#16a34a', fontWeight: 700, fontSize: '0.78rem' }}>✅ Farmer verified via OTP</p>
                    <p style={{ margin: 0, fontSize: '0.65rem', color: '#6b7280' }}>
                      Settlement uses: <strong>{Number(billingArea).toFixed(2)} ac</strong>
                    </p>
                    {act.farmer_response_at && (
                      <p style={{ margin: '3px 0 0', fontSize: '0.6rem', color: '#9ca3af' }}>
                        Verified: {new Date(act.farmer_response_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                      </p>
                    )}
                  </>
                )}

                {verifyStatus === 'disputed' && (
                  <>
                    <p style={{ margin: '0 0 8px', color: '#dc2626', fontWeight: 700, fontSize: '0.78rem' }}>❌ Disputed</p>

                    {/* Comparison: Mukkadam vs Farmer */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '8px' }}>
                      <div style={{ background: '#eff6ff', borderRadius: '6px', padding: '6px 8px', textAlign: 'center' }}>
                        <p style={{ margin: '0 0 2px', fontSize: '0.58rem', color: '#6b7280', fontWeight: 600 }}>MUKKADAM</p>
                        <p style={{ margin: 0, fontWeight: 800, color: '#1d4ed8', fontSize: '0.88rem' }}>{mukkadamClaimed != null ? `${Number(mukkadamClaimed).toFixed(2)} ac` : '—'}</p>
                      </div>
                      <div style={{ background: act.admin_override_area != null ? '#fff7ed' : '#fef2f2', borderRadius: '6px', padding: '6px 8px', textAlign: 'center' }}>
                        <p style={{ margin: '0 0 2px', fontSize: '0.58rem', color: '#6b7280', fontWeight: 600 }}>FARMER</p>
                        <p style={{ margin: 0, fontWeight: 800, color: act.admin_override_area != null ? '#d97706' : '#dc2626', fontSize: '0.88rem' }}>
                          {act.admin_override_area != null ? `${Number(act.admin_override_area).toFixed(2)} ac` : '—'}
                        </p>
                      </div>
                    </div>

                    {act.admin_override_area != null ? (
                      <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px', padding: '5px 8px', fontSize: '0.68rem', color: '#16a34a', fontWeight: 700, marginBottom: '8px' }}>
                        ✓ Billing using farmer's claim: {Number(act.admin_override_area).toFixed(2)} ac
                        {act.dispute_reason ? <span style={{ color: '#6b7280', fontWeight: 400 }}> — {act.dispute_reason}</span> : ''}
                      </div>
                    ) : (
                      <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', padding: '5px 8px', fontSize: '0.68rem', color: '#dc2626', fontWeight: 600, marginBottom: '8px' }}>
                        🔒 Billing locked — call farmer &amp; fill claim below
                      </div>
                    )}

                    {act.farmer_dispute_reason && (
                      <p style={{ margin: '0 0 8px', fontSize: '0.68rem', color: '#374151', background: '#fef2f2', padding: '5px 7px', borderRadius: '5px' }}>
                        "{act.farmer_dispute_reason}"
                      </p>
                    )}

                    {/* OTP section */}
                    <div style={{ borderTop: '1px solid #fecaca', paddingTop: '8px', marginTop: '4px' }}>
                      <p style={{ margin: '0 0 6px', fontSize: '0.62rem', color: '#6b7280', fontWeight: 600 }}>RE-VERIFY VIA OTP</p>
                      {otpOpen === act.allocation_id ? (
                        <div style={{ display: 'flex', gap: '5px' }}>
                          <input
                            type="text"
                            inputMode="numeric"
                            value={otpCode}
                            onChange={e => setOtpCode(e.target.value)}
                            placeholder="Enter OTP"
                            maxLength={6}
                            style={{ flex: 1, padding: '6px 10px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '0.9rem', fontWeight: 700, letterSpacing: '0.15em', textAlign: 'center' }}
                          />
                          <button
                            onClick={() => handleVerifyOtp(act.allocation_id, farmerId)}
                            disabled={otpVerifying || !otpCode.trim()}
                            style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: otpVerifying ? '#99f6e4' : '#14b8a6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
                          >
                            {otpVerifying ? '...' : '✓ Verify'}
                          </button>
                          <button
                            onClick={() => { setOtpOpen(null); setOtpCode(''); }}
                            style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.72rem', cursor: 'pointer' }}
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleSendOtp(act.allocation_id)}
                          disabled={otpSending === act.allocation_id}
                          style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', color: '#374151', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer' }}
                        >
                          {otpSending === act.allocation_id ? 'Sending...' : '📱 Send OTP to Farmer'}
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Duration bar */}
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
              // Only sum 'calculated' jobs with positive net_payable — skip paid/no_payment_needed
              const totalNet = m.settlements
                .filter((s2: any) => s2.status === 'calculated' && Number(s2.net_payable) > 0.01)
                .reduce((s: number, s2: any) => s + Number(s2.net_payable), 0);
              return sum + totalNet;
            }, 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,
            suffix: 'to mukkadams', color: '#dc2626', bg: '#fef2f2', border: '#fecaca'
          },
        ].map(s => (
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
          { key: 'farmers', label: '🌾 Farmer Collections', count: data.farmers.filter((f: any) => {
    const allAllocs = (f.jobs || [f]).flatMap((j: any) =>
      (j.activities || []).flatMap((a: any) => a.allocations || [])
    );
    if (allAllocs.length === 0) return true;
    return allAllocs.some((a: any) => a.work_status !== 'work_not_started');
  }).length, color: '#3b82f6' },
          { key: 'mukkadams', label: '👷 Mukkadam Settlements', count: data.mukkadams.filter((m: any) => {
    const allAllocs = (m.settlements || []).flatMap((s: any) => s.activities || []);
    if (allAllocs.length === 0) return true;
    return allAllocs.some((a: any) => a.work_status !== 'work_not_started');
  }).length, color: '#0f766e' },
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
            <span style={{ marginLeft: '6px', fontSize: '0.65rem', padding: '1px 6px', borderRadius: '999px', background: tab === t.key ? t.color : '#f3f4f6', color: tab === t.key ? '#fff' : '#6b7280', fontWeight: 700 }}>
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
            {data.farmers.filter((f: any) => {
                const allAllocs = (f.jobs || [f]).flatMap((j: any) => (j.activities || []).flatMap((a: any) => a.allocations || []));
                if (allAllocs.length === 0) return true;
                return allAllocs.some((a: any) => a.work_status !== 'work_not_started');
              }).length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af', fontSize: '0.82rem' }}>
                No active farmer jobs (all work not started yet)
              </div>
            ) : data.farmers.filter((f: any) => {
                // Hide farmers where NO allocation has started work yet
                const allAllocs = (f.jobs || [f]).flatMap((j: any) =>
                  (j.activities || []).flatMap((a: any) => a.allocations || [])
                );
                if (allAllocs.length === 0) return true; // no allocs yet — show anyway
                return allAllocs.some((a: any) => a.work_status !== 'work_not_started');
              }).map((f: any) => {
              // Support both old flat structure (f.summary) and new grouped structure (f.jobs)
              const jobs = f.jobs || [f];
              const totalBalance = jobs.reduce((s: number, j: any) => s + (j.summary?.balance_due || 0), 0);
              const totalAmount  = jobs.reduce((s: number, j: any) => s + (j.total_job_amount || j.booking_total || 0), 0);
              const firstDate    = jobs.reduce((d: string | null, j: any) => {
                const fd = j.first_activity_date || j.activities?.[0]?.scheduled_date;
                return (!d || (fd && fd < d)) ? fd : d;
              }, null as string | null);
              const lastDate     = jobs.reduce((d: string | null, j: any) => {
                const ld = j.last_activity_date || j.activities?.[j.activities?.length - 1]?.scheduled_date;
                return (!d || (ld && ld > d)) ? ld : d;
              }, null as string | null);

              const hasBalance = totalBalance > 0.01;

              // Pending verifications across all jobs
              const pendingVerify = jobs.reduce((n: number, j: any) =>
                n + (j.activities || []).filter((a: any) =>
                  a.report_submitted && a.farmer_agreed === null
                ).length, 0);

              // Dispute count
              const disputeCount = jobs.reduce((n: number, j: any) =>
                n + (j.activities || []).flatMap((a: any) => a.allocations || []).filter((a: any) =>
                  a.payment_status === 'dispute'
                ).length, 0);

              const expandKey = `farmer-${f.farmer_id}`;
              const isOpen = expandedKey === expandKey;

              return (
                <div key={expandKey} style={{
                  border: `1.5px solid ${disputeCount > 0 ? '#fecaca' : pendingVerify > 0 ? '#fde68a' : hasBalance ? '#fde68a' : '#e5e7eb'}`,
                  borderRadius: '12px', background: '#fff', overflow: 'hidden',
                }}>
                  {/* ── COLLAPSED HEADER ── */}
                  <div
                    onClick={() => setExpandedKey(isOpen ? null : expandKey)}
                    style={{ padding: '12px 16px', cursor: 'pointer' }}
                  >
                    {/* Row 1: name + badges + collect button */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#111827' }}>{f.farmer_name}</span>
                          <span style={{ fontSize: '0.65rem', color: '#9ca3af' }}>{f.farmer_id}</span>
                          <span style={{
                            fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 600,
                            background: hasBalance ? '#fef9c3' : '#dcfce7',
                            color: hasBalance ? '#b45309' : '#16a34a',
                          }}>
                            {hasBalance ? '⚠ Balance Due' : '✓ Clear'}
                          </span>
                          {disputeCount > 0 && (
                            <span style={{ fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: '#fef2f2', color: '#dc2626' }}>
                              🚨 {disputeCount} Dispute{disputeCount > 1 ? 's' : ''}
                            </span>
                          )}
                          {pendingVerify > 0 && (
                            <span style={{ fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: '#fef9c3', color: '#b45309' }}>
                              👀 {pendingVerify} Verify Pending
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: '#6b7280', marginTop: '3px' }}>
                          📞 {f.phone_number || f.mobile_number || '—'}
                        </div>
                        {(firstDate || lastDate) && (
                          <div style={{ fontSize: '0.65rem', color: '#9ca3af', marginTop: '2px' }}>
                            📅 {firstDate || '—'} → {lastDate || '—'}
                          </div>
                        )}
                      </div>

                      {/* Right: financial summary grid + collect button */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }} onClick={e => e.stopPropagation()}>
                        {/* 3-number summary */}
                        <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-end' }}>
                          {jobs.map((j: any) => {
                            const s = j.summary;
                            if (!s) return null;
                            const advance = s.advance_paid || 0;
                            const billed = s.total_billable_so_far || 0;
                            const toCollect = s.balance_due || 0;
                            const totalJob = j.total_job_amount || 0;
                            return (
                              <div key={j.job_id} style={{ display: 'flex', gap: '14px' }}>
                                <div style={{ textAlign: 'right' }}>
                                  <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>Total Job</div>
                                  <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#374151' }}>₹{totalJob.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                  <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>Billed</div>
                                  <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#0f766e' }}>₹{billed.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                  <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>Collected</div>
                                  <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#16a34a' }}>₹{(s.total_paid || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                  <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>To Collect</div>
                                  <div style={{ fontWeight: 800, fontSize: '0.92rem', color: toCollect > 0.01 ? '#dc2626' : '#16a34a' }}>
                                    {toCollect > 0.01 ? `₹${toCollect.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '✓ Clear'}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        {/* Collect button(s) */}
                        {jobs.map((j: any) => {
                          const s = j.summary;
                          if (!s || s.balance_due <= 0.01) return null;
                          return (
                            <button
                              key={j.job_id}
                              onClick={() => {
                                setPayModal({ farmerId: f.farmer_id, jobId: j.job_id, amount: Math.round(s.balance_due), farmerName: f.farmer_name, existingPayments: j.payment_history || [] });
                                setPayAmount(String(Math.round(s.balance_due)));
                                setPayMode('CASH'); setPayNotes(''); setProofFile(null);
                              }}
                              style={{ padding: '5px 14px', borderRadius: '7px', border: 'none', background: '#3b82f6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
                            >
                              + Collect ₹{Math.round(s.balance_due).toLocaleString('en-IN')}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Row 2: per-job work status counts */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      {jobs.map((j: any) => {
                        const allAllocs = (j.activities || []).flatMap((a: any) => a.allocations || []);
                        const counts: Record<string, number> = {};
                        allAllocs.forEach((a: any) => {
                          const ws = a.work_status || 'work_not_started';
                          counts[ws] = (counts[ws] || 0) + 1;
                        });
                        return (
                          <div key={j.job_id} style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.6rem', color: '#9ca3af', fontFamily: 'monospace' }}>#{j.job_id}</span>
                            {counts.work_not_started > 0 && <span style={{ fontSize: '0.6rem', background: '#f3f4f6', color: '#6b7280', padding: '1px 5px', borderRadius: '999px' }}>{counts.work_not_started} not started</span>}
                            {counts.in_progress > 0 && <span style={{ fontSize: '0.6rem', background: '#dbeafe', color: '#1d4ed8', padding: '1px 5px', borderRadius: '999px' }}>{counts.in_progress} in progress</span>}
                            {counts.completed > 0 && <span style={{ fontSize: '0.6rem', background: '#dcfce7', color: '#16a34a', padding: '1px 5px', borderRadius: '999px' }}>{counts.completed} completed</span>}
                          </div>
                        );
                      })}
                      <span style={{ marginLeft: 'auto', color: '#9ca3af', fontSize: '0.65rem' }}>{isOpen ? '▲' : '▼'}</span>
                    </div>
                  </div>

                  {/* ── EXPANDED ── */}
                  {isOpen && jobs.map((j: any) => {
                    const s = j.summary;
                    const hasJobBalance = s && s.balance_due > 0.01;

                    return (
                      <div key={j.job_id} style={{ borderTop: '1px solid #e5e7eb', background: '#fafafa', padding: '14px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                          <div>
                            <span style={{ fontWeight: 700, fontSize: '0.82rem', color: '#374151' }}>{j.crop_name}</span>
                            {j.variety && <span style={{ fontSize: '0.72rem', color: '#9ca3af', marginLeft: '6px' }}>({j.variety})</span>}
                            {j.plot_name && <span style={{ fontSize: '0.72rem', color: '#6b7280', marginLeft: '6px' }}>{j.plot_name}</span>}
                          </div>
                          <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', color: '#9ca3af' }}>#{j.job_id}</span>
                        </div>

                        {/* ── PAYMENT SECTION FIRST ── */}
                        {s && (
                          <div style={{ background: '#fff', borderRadius: '10px', border: '1px solid #e5e7eb', padding: '12px 14px', marginBottom: '14px' }}>
                            <p style={{ margin: '0 0 10px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>💰 Payment Summary</p>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>

                              {/* Calculation */}
                              <div style={{ background: '#f9fafb', borderRadius: '8px', padding: '10px 12px', fontSize: '0.74rem' }}>
                                {[
                                  { label: 'Total Billed So Far', val: `₹${s.total_billable_so_far.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e' },
                                  { label: '− Total Collected',   val: `−₹${s.total_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#16a34a' },
                                ].map((row, ri) => (
                                  <div key={ri} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                                    <span style={{ color: '#6b7280' }}>{row.label}</span>
                                    <span style={{ fontWeight: 700, color: row.color }}>{row.val}</span>
                                  </div>
                                ))}
                                <div style={{ borderTop: '1.5px solid #e5e7eb', paddingTop: '6px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                                  <span style={{ color: '#111827' }}>Balance Due</span>
                                  <span style={{ color: hasJobBalance ? '#dc2626' : '#16a34a', fontSize: '0.9rem' }}>
                                    {hasJobBalance ? `₹${s.balance_due.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '✓ Clear'}
                                  </span>
                                </div>
                                {s.all_activities_past && s.final_gap > 0 && (
                                  <div style={{ marginTop: '6px', padding: '6px 8px', borderRadius: '6px', background: '#fef2f2', border: '1px solid #fecaca', fontSize: '0.68rem', color: '#dc2626', fontWeight: 700 }}>
                                    ⚠ All done — ₹{s.final_gap.toLocaleString('en-IN', { maximumFractionDigits: 0 })} vs booking total
                                  </div>
                                )}
                              </div>

                              {/* Payment history */}
                              <div style={{ background: '#f9fafb', borderRadius: '8px', padding: '10px 12px', fontSize: '0.74rem' }}>
                                <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📅 History</p>
                                {(j.payment_history || []).length === 0 ? (
                                  <p style={{ color: '#9ca3af', fontSize: '0.72rem', margin: 0 }}>No payments recorded</p>
                                ) : (
                                  <>
                                    {(j.payment_history || []).map((p: any, pi: number) => (
                                      <div key={pi} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '4px', marginBottom: '4px', borderBottom: pi < j.payment_history.length - 1 ? '1px solid #f3f4f6' : 'none' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexWrap: 'wrap' }}>
                                          <span style={{ fontSize: '0.6rem', padding: '1px 5px', borderRadius: '999px', background: p.type === 'advance' ? '#eff6ff' : '#f0fdf4', color: p.type === 'advance' ? '#1d4ed8' : '#16a34a', fontWeight: 600 }}>{p.mode}</span>
                                          <span style={{ color: '#9ca3af', fontSize: '0.64rem' }}>{p.date}</span>
                                          {p.proof_url && (
                                            <a href={p.proof_url} target="_blank" rel="noreferrer"
                                              style={{ fontSize: '0.58rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0px 5px', background: '#eff6ff', cursor: 'pointer' }}
                                              title="View payment proof">
                                              📎 View
                                            </a>
                                          )}
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

                            {hasJobBalance && (
                              <button
                                onClick={() => {
                                  setPayModal({ farmerId: f.farmer_id, jobId: j.job_id, amount: Math.round(s.balance_due), farmerName: f.farmer_name, existingPayments: j.payment_history || [] });
                                  setPayAmount(String(Math.round(s.balance_due)));
                                  setPayMode('CASH'); setPayNotes(''); setProofFile(null);
                                }}
                                style={{ width: '100%', padding: '10px', borderRadius: '8px', border: 'none', background: '#3b82f6', color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' }}
                              >
                                + Collect ₹{Math.round(s.balance_due).toLocaleString('en-IN')} from {f.farmer_name}
                              </button>
                            )}
                          </div>
                        )}

                        {/* ── WORK ALLOCATIONS BELOW PAYMENT ── */}
                        <p style={{ margin: '0 0 8px', fontSize: '0.68rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                          📋 Work Allocations & Verification
                        </p>
                        <div style={{ display: 'grid', gridTemplateColumns: '2fr 0.8fr 1fr 1fr 1fr auto', gap: '8px', padding: '4px 12px', fontSize: '0.6rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>
                          <span>Activity / Status</span>
                          <span style={{ textAlign: 'center' }}>Date</span>
                          <span style={{ textAlign: 'center' }}>BI Assigned</span>
                          <span style={{ textAlign: 'center' }}>Mukkadam</span>
                          <span style={{ textAlign: 'center' }}>Farmer</span>
                          <span />
                        </div>

                        {(j.activities || []).flatMap((act: any) =>
                          (act.allocations || [{ ...act, allocation_id: act.activity_id }]).map((alloc: any) => (
                            <AllocReportCard
                              key={alloc.allocation_id}
                              act={{ ...act, ...alloc }}
                              farmerId={f.farmer_id}
                            />
                          ))
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        )}

        {/* ════ MUKKADAMS TAB ════ */}
        {tab === 'mukkadams' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {data.mukkadams.filter((m: any) => {
                const allAllocs = (m.settlements || []).flatMap((s: any) => s.activities || []);
                if (allAllocs.length === 0) return true;
                return allAllocs.some((a: any) => a.work_status !== 'work_not_started');
              }).length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af', fontSize: '0.82rem' }}>
                No active mukkadams (all work not started yet)
              </div>
            ) : // Replace the mukkadam filter:
data.mukkadams.filter((m: any) => {
  // Always show if weekly payment is due today
  if (m.already_paid_today === false && m.weekly_payment_day_value !== null && m.weekly_payment_day_value !== undefined) {
    const todayJs = new Date().getDay();
    const todayPy = todayJs === 0 ? 6 : todayJs - 1;
    if (m.weekly_payment_day_value === todayPy) return true;
  }
  // Always show if has advance given
  if (m.advance_amount > 0) return true;
  // Always show if has any settlements
  if (m.settlements && m.settlements.length > 0) return true;
  // Otherwise hide if no work started
  const allAllocs = (m.settlements || []).flatMap((s: any) => s.activities || []);
  if (allAllocs.length === 0) return false; // no settlements, no advance, no weekly due → hide
  return allAllocs.some((a: any) => a.work_status !== 'work_not_started');
}).map((m: any) => {
              const expandKey = `mukkadam-${m.mukkadam_id}`;
              const isOpen = expandedKey === expandKey;

              const weeklyPaymentDayValue = m.weekly_payment_day_value ?? m.assignment?.weekly_payment_day_value;
              const weeklyPaymentAmount   = m.weekly_payment_amount   ?? m.assignment?.weekly_payment_amount;
              const weeklyPaymentDayLabel = m.weekly_payment_day_label ?? m.assignment?.weekly_payment_day_label;
              const alreadyPaidToday      = m.already_paid_today      ?? m.assignment?.already_paid_today;
              const assignmentId          = m.assignment_id            ?? m.assignment?.assignment_id;
              const totalWeeklyPaid       = m.total_weekly_paid        ?? 0;
              const transportPrice        = m.transport_price          ?? 0;
              const advancePaid           = m.advance_amount           ?? 0;

              const todayJs = new Date().getDay();
              const todayPy = todayJs === 0 ? 6 : todayJs - 1;
              const weeklyDueToday = weeklyPaymentDayValue === todayPy && !alreadyPaidToday;

              // ── OVERALL CALCULATION ──────────────────────────────────────────
              // Backend already handles carry-forward, advance absorption, weekly deduction correctly
              // Just sum net_payable from 'calculated' jobs (backend already deducted advance+weekly once)
              const totalGross = m.settlements.reduce((acc: number, st: any) => acc + Number(st.gross_amount), 0);
              // Deposit: held until ALL activities in that job are work_status='completed'
              // Paying 90% (status=paid) does NOT release 10% — only all-activities-done releases it
              const isJobFullyDone = (st: any) => {
                const acts = st.activities || [];
                return acts.length > 0 && acts.every((a: any) => a.work_status === 'completed');
              };
              const depositHeld = m.settlements
                .filter((st: any) => !isJobFullyDone(st))
                .reduce((acc: number, st: any) => acc + Number(st.deposit_held || 0), 0);
              // 90% payable from all settled jobs for display only
              const payableFromSettled = m.settlements
                .filter((st: any) => st.status === 'calculated' || st.status === 'paid')
                .reduce((acc: number, st: any) => acc + Number(st.payable_90pct), 0);
              const totalMisc = m.settlements.reduce((acc: number, st: any) => acc + Number(st.total_misc || 0), 0);
              // SAFETY CHECK: shoot selection must be completed for a job to be payable
              // If settlement is 'calculated' but shoot selection activity is NOT completed
              // → stale settlement (activities were reset after calculation) → block payment
              const isShootSelectionDone = (st: any) => {
                const acts = st.activities || [];
                return acts.some((a: any) => {
                  const name = (a.activity_name || '').toLowerCase();
                  return ((name.includes('shoot') && name.includes('select')) ||
                         (a.activity_name || '').includes('विरळणी')) &&
                         a.work_status === 'completed';
                });
              };

              // Only count jobs where shoot selection is genuinely done
              const netPayableOverall = m.settlements
                .filter((st: any) => st.status === 'calculated' && isShootSelectionDone(st))
                .reduce((acc: number, st: any) => acc + Number(st.net_payable), 0);

              const jobsReadyToPay = m.settlements.filter((st: any) =>
                st.status === 'calculated' &&
                Number(st.net_payable) > 0.01 &&
                isShootSelectionDone(st)
              );

              // Jobs with stale settlement (calculated but shoot not done) — show warning
              const staleSettlements = m.settlements.filter((st: any) =>
                st.status === 'calculated' && !isShootSelectionDone(st)
              );

              const canPay = netPayableOverall > 0.01 && jobsReadyToPay.length > 0;
              const hasDue = canPay;

              return (
                <div key={expandKey} style={{ border: `1.5px solid ${hasDue ? '#fde68a' : '#e5e7eb'}`, borderRadius: '12px', background: '#fff', overflow: 'hidden' }}>

                  {/* ── COLLAPSED HEADER ── */}
                  <div onClick={() => setExpandedKey(isOpen ? null : expandKey)} style={{ padding: '12px 16px', cursor: 'pointer' }}>
                    {/* Row 1: name + contact + weekly badge */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#111827' }}>{m.mukkadam_name}</span>
                          {weeklyDueToday && (
                            <span style={{ fontSize: '0.6rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: '#fef9c3', color: '#b45309' }}>📅 Weekly Due</span>
                          )}
                        </div>
                        <div style={{ fontSize: '0.66rem', color: '#6b7280', marginTop: '2px' }}>
                          📞 {m.mobile || m.mobile_numbers || '—'} · {m.crew_size} workers
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }} onClick={e => e.stopPropagation()}>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: '0.6rem', color: '#9ca3af', textTransform: 'uppercase', fontWeight: 600 }}>Net Payable</div>
                          <div style={{ fontWeight: 800, fontSize: '1.1rem', color: canPay ? '#dc2626' : netPayableOverall < -0.01 ? '#16a34a' : '#6b7280' }}>
                            {canPay ? `₹${netPayableOverall.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : netPayableOverall < -0.01 ? '✓ In Credit' : '—'}
                          </div>
                        </div>
                        {canPay && jobsReadyToPay.map((st: any) => (
                          <button key={st.job_id}
                            onClick={() => handleMukkadamPay(m.mukkadam_id, st.job_id, netPayableOverall, m.mukkadam_name)}
                            disabled={mukkadamPaying === `${m.mukkadam_id}-${st.job_id}`}
                            style={{ padding: '5px 10px', borderRadius: '7px', border: 'none', background: '#14b8a6', color: '#fff', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                            🏦 Pay ₹{netPayableOverall.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </button>
                        ))}
                        {weeklyDueToday && (
                          <button onClick={() => handleAddWeeklyPayment(m.mukkadam_id, assignmentId, weeklyPaymentAmount, m.mukkadam_name)}
                            style={{ padding: '5px 10px', borderRadius: '7px', border: 'none', background: '#d97706', color: '#fff', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer' }}>
                            + Weekly ₹{Number(weeklyPaymentAmount).toLocaleString('en-IN')}
                          </button>
                        )}
                        
{(m.missed_weekly_dates || []).length > 0 && (
  <span style={{ fontSize: '0.6rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: '#fef2f2', color: '#dc2626' }}>
    ⚠️ {m.missed_weekly_dates.length} missed payment{m.missed_weekly_dates.length > 1 ? 's' : ''}
  </span>
)}
                      </div>
                    </div>

                    {/* Overall financial summary grid */}
                    {(() => {
                      // Total paid out across all settlements
                      const totalPaidOut = m.settlements.reduce((acc: number, st: any) =>
                        acc + (st.payments_made || []).reduce((s: number, p: any) => s + Number(p.amount), 0), 0);
                      const totalNetPayable = m.settlements.reduce((acc: number, st: any) => acc + Number(st.net_payable || 0), 0);
                      const remaining = totalNetPayable - totalPaidOut;

                      return (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '6px', marginTop: '10px', padding: '8px 10px', background: '#f9fafb', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
                      {[
                        { label: 'Gross Earned', val: `₹${totalGross.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e' },
                        { label: '10% Deposit', val: (() => {
                            const totalDeposit = m.settlements.reduce((acc: number, st: any) => acc + Number(st.deposit_held || 0), 0);
                            if (depositHeld <= 0 && totalDeposit > 0) return `✓ ₹${totalDeposit.toLocaleString('en-IN', { maximumFractionDigits: 0 })} released`;
                            if (depositHeld <= 0) return '—';
                            return `₹${depositHeld.toLocaleString('en-IN', { maximumFractionDigits: 0 })} held`;
                          })(), color: depositHeld > 0 ? '#b45309' : '#16a34a' },
                        { label: 'Advance', val: `−₹${Number(advancePaid).toLocaleString('en-IN')}`, color: '#dc2626' },
                        { label: 'Weekly Paid', val: `−₹${Number(totalWeeklyPaid).toLocaleString('en-IN')}`, color: '#dc2626' },
                        { label: 'Settlement Paid', val: totalPaidOut > 0 ? `−₹${totalPaidOut.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—', color: totalPaidOut > 0 ? '#16a34a' : '#9ca3af' },
                        { label: 'Remaining', val: remaining > 0.01 ? `₹${remaining.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : remaining < -0.01 ? '✓ clear' : '✓ Clear', color: remaining > 0.01 ? '#dc2626' : '#16a34a' },
                      ].map((item, i) => (
                        <div key={i} style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '0.56rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', marginBottom: '2px' }}>{item.label}</div>
                          <div style={{ fontSize: '0.78rem', fontWeight: 700, color: item.color }}>{item.val}</div>
                        </div>
                      ))}
                    </div>
                      );
                    })()}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
                      <span style={{ color: '#9ca3af', fontSize: '0.62rem' }}>{isOpen ? '▲' : '▼'} Details</span>
                    </div>
                  </div>

                  {/* ── EXPANDED ── */}
                  {isOpen && (
                    <div style={{ borderTop: '1px solid #e5e7eb', padding: '14px 16px', background: '#fafafa', display: 'flex', flexDirection: 'column', gap: '12px' }}>

                      {/* ── 1. OVERALL FINANCIAL SUMMARY ── */}
                      <div style={{ background: '#fff', borderRadius: '10px', border: '1px solid #e5e7eb', padding: '12px 14px' }}>
                        <p style={{ margin: '0 0 10px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📊 Overall Settlement</p>
                        <div style={{ fontSize: '0.76rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {/* Per-job breakdown rows */}
                          {m.settlements.map((st: any) => {
                            const stMeta = STATUS_META[st.status] || STATUS_META.pending;
                            return (
                              <div key={st.job_id} style={{ background: '#f9fafb', borderRadius: '6px', padding: '6px 10px', marginBottom: '2px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                                  <span style={{ fontWeight: 700, color: '#374151', fontSize: '0.72rem' }}>#{st.job_id} {st.farmer_name}</span>
                                  <span style={{ fontSize: '0.58rem', padding: '1px 6px', borderRadius: '999px', background: stMeta.bg, color: stMeta.text, fontWeight: 700 }}>{stMeta.label}</span>
                                </div>
                                {[
                                  { label: 'Gross',              val: `₹${Number(st.gross_amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,    color: '#0f766e' },
                                  { label: (() => { const acts = st.activities || []; const allDone = acts.length > 0 && acts.every((a: any) => a.work_status === 'completed'); return allDone ? '+ 10% released ✓' : '− 10% deposit held'; })(), val: (() => { const acts = st.activities || []; const allDone = acts.length > 0 && acts.every((a: any) => a.work_status === 'completed'); return (allDone ? '+' : '−') + `₹${Number(st.deposit_held).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`; })(), color: (() => { const acts = st.activities || []; return acts.length > 0 && acts.every((a: any) => a.work_status === 'completed') ? '#16a34a' : '#b45309'; })() },
                                  { label: '= 90% payable',      val: `₹${Number(st.payable_90pct).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,   color: '#1f2937' },
                                  ...(st.deposit_carried_forward > 0  ? [{ label: '+ Deposit from prev job', val: `+₹${Number(st.deposit_carried_forward).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e' }] : []),
                                  ...(st.credit_carried_forward > 0   ? [{ label: '− Credit to next job',    val: `−₹${Number(st.credit_carried_forward).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#6b7280' }] : []),
                                  ...(st.advance_deducted > 0         ? [{ label: '− Advance (this job)',    val: `−₹${Number(st.advance_deducted).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,         color: '#dc2626' }] : []),
                                  ...(st.weekly_payments_deducted > 0 ? [{ label: '− Weekly payments',      val: `−₹${Number(st.weekly_payments_deducted).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#dc2626' }] : []),
                                  ...(st.total_misc > 0               ? [{ label: '− Misc costs',           val: `−₹${Number(st.total_misc).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,               color: '#dc2626' }] : []),
                                ].map((row, ri) => (
                                  <div key={ri} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', paddingBottom: '1px' }}>
                                    <span style={{ color: '#9ca3af' }}>{row.label}</span>
                                    <span style={{ fontWeight: 600, color: row.color }}>{row.val}</span>
                                  </div>
                                ))}
                                {/* Net row */}
                                <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #e5e7eb', paddingTop: '3px', marginTop: '3px', fontSize: '0.72rem', fontWeight: 800 }}>
                                  <span>Net</span>
                                  <span style={{ color: Number(st.net_payable) > 0.01 ? '#dc2626' : '#6b7280' }}>
                                    {Number(st.net_payable) > 0.01
                                      ? `To Pay ₹${Number(st.net_payable).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
                                      : st.status === 'no_payment_needed' ? 'Credit → carried forward' : '₹0'}
                                  </span>
                                </div>

                                {/* Payments made against this settlement */}
                                {(st.payments_made || []).length > 0 && (
                                  <div style={{ marginTop: '4px', borderTop: '1px dashed #e5e7eb', paddingTop: '4px' }}>
                                    {(st.payments_made || []).map((pay: any, pi: number) => (
                                      <div key={pi} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.67rem', paddingBottom: '2px' }}>
                                        <span style={{ color: '#6b7280' }}>
                                          ✅ Paid {pay.paid_at} · {pay.mode}
                                          {pay.notes ? ` · ${pay.notes}` : ''}
                                        </span>
                                        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                          <span style={{ fontWeight: 700, color: '#16a34a' }}>
                                            −₹{Number(pay.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                          </span>
                                          {pay.proof_url && (
                                            <a href={pay.proof_url} target="_blank" rel="noreferrer"
                                              style={{ fontSize: '0.6rem', color: '#3b82f6', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0 4px', background: '#eff6ff', textDecoration: 'none' }}>
                                              📎
                                            </a>
                                          )}
                                        </span>
                                      </div>
                                    ))}
                                    {/* Remaining after payments */}
                                    {Number(st.total_already_paid) > 0 && (
                                      <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #e5e7eb', paddingTop: '3px', marginTop: '2px', fontSize: '0.72rem', fontWeight: 800 }}>
                                        <span style={{ color: '#374151' }}>Remaining</span>
                                        <span style={{ color: (Number(st.net_payable) - Number(st.total_already_paid)) > 0.01 ? '#dc2626' : '#16a34a' }}>
                                          {(Number(st.net_payable) - Number(st.total_already_paid)) > 0.01
                                            ? `₹${(Number(st.net_payable) - Number(st.total_already_paid)).toLocaleString('en-IN', { maximumFractionDigits: 0 })} still due`
                                            : `✓ Fully Paid`}
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}

                          {/* Final net across all jobs */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 10px', background: canPay ? '#fef2f2' : '#f0fdf4', borderRadius: '8px', border: `1px solid ${canPay ? '#fecaca' : '#bbf7d0'}`, fontWeight: 800, marginTop: '4px' }}>
                            <span style={{ color: '#111827', fontSize: '0.84rem' }}>Net Payable Now</span>
                            <span style={{ fontSize: '1rem', color: canPay ? '#dc2626' : '#16a34a' }}>
                              {canPay
                                ? `₹${netPayableOverall.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
                                : `✓ ₹0`}
                            </span>
                          </div>
                          {!canPay && m.settlements.some((st: any) => st.status === 'no_payment_needed') && (
                            <p style={{ margin: '2px 0 0', fontSize: '0.64rem', color: '#16a34a' }}>✓ Credit from earlier jobs absorbed — no payment needed</p>
                          )}
                          {staleSettlements.length > 0 && (
                            <div style={{ marginTop: '6px', background: '#fef9c3', border: '1px solid #fde047', borderRadius: '7px', padding: '8px 12px' }}>
                              <p style={{ margin: '0 0 4px', fontSize: '0.64rem', fontWeight: 700, color: '#854d0e', textTransform: 'uppercase' }}>⚠️ Stale Settlement Detected</p>
                              {staleSettlements.map((st: any) => (
                                <div key={st.job_id} style={{ fontSize: '0.68rem', color: '#713f12' }}>
                                  Job #{st.job_id} ({st.farmer_name}) — settlement shows ₹{Number(st.net_payable).toLocaleString('en-IN')} but shoot selection is NOT completed.
                                  Activities were reset after settlement was calculated.
                                </div>
                              ))}
                              <p style={{ margin: '4px 0 0', fontSize: '0.64rem', color: '#854d0e' }}>
                                👉 Go to Django Admin → MukkadamJobSettlement → reset status to 'pending' for these jobs, then recalculate when shoot selection is done.
                              </p>
                            </div>
                          )}
                          {canPay && jobsReadyToPay.map((st: any) => (
                            <button key={st.job_id}
                              onClick={() => handleMukkadamPay(m.mukkadam_id, st.job_id, netPayableOverall, m.mukkadam_name)}
                              disabled={mukkadamPaying === `${m.mukkadam_id}-${st.job_id}`}
                              style={{ width: '100%', marginTop: '4px', padding: '10px', borderRadius: '8px', border: 'none', background: '#14b8a6', color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' }}>
                              🏦 Pay ₹{netPayableOverall.toLocaleString('en-IN', { maximumFractionDigits: 0 })} to {m.mukkadam_name}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* ── 2. WEEK-WISE LEDGER ── */}
                      {(() => {
                        const ledger: any[] = m.week_ledger || [];
                        const pendingWork: any[] = m.pending_work || [];

                        if (ledger.length === 0 && pendingWork.length === 0) return (
                          <div style={{ padding: '10px 14px', background: '#f9fafb', borderRadius: '8px', fontSize: '0.72rem', color: '#9ca3af', textAlign: 'center' }}>
                            No weekly payments recorded yet
                          </div>
                        );

                        return (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <p style={{ margin: '0 0 4px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📅 Week-wise Running Ledger</p>

                            {ledger.map((row: any, ri: number) => {
                              const isAdvance  = row.type === 'advance';
                              const isPositive = row.running_balance >= 0;
                              const events: any[] = row.billing_events || [];

                              return (
                                <div key={ri} style={{
                                  background: '#fff',
                                  borderRadius: '8px',
                                  border: `1px solid ${row.can_pay ? '#fde68a' : isAdvance ? '#fecaca' : '#e5e7eb'}`,
                                  overflow: 'hidden'
                                }}>
                                  {/* Row header */}
                                  <div style={{
                                    background: isAdvance ? '#fef2f2' : '#f9fafb',
                                    padding: '7px 12px',
                                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                    borderBottom: events.length > 0 || pendingWork.length > 0 ? '1px solid #e5e7eb' : 'none'
                                  }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                      {isAdvance ? (
                                        <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#dc2626' }}>💰 Advance Given</span>
                                      ) : (
                                        <>
                                          <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#374151' }}>Week {row.week_num} · {row.payment_date}</span>
                                          <span style={{ fontSize: '0.6rem', padding: '1px 7px', borderRadius: '999px', background: '#fef2f2', color: '#dc2626', fontWeight: 600 }}>
                                            Weekly −₹{Number(row.weekly_paid).toLocaleString('en-IN')}
                                          </span>
                                          {row.weekly_proof_url && (
                                            <a href={row.weekly_proof_url} target="_blank" rel="noreferrer"
                                              style={{ fontSize: '0.58rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0 4px', background: '#eff6ff' }}>📎</a>
                                          )}
                                          {row.payable_this_week > 0 && (
                                            <span style={{ fontSize: '0.6rem', padding: '1px 7px', borderRadius: '999px', background: '#f0fdf4', color: '#16a34a', fontWeight: 600 }}>
                                              +₹{Number(row.payable_this_week).toLocaleString('en-IN')} earned
                                            </span>
                                          )}
                                        </>
                                      )}
                                    </div>
                                    {/* Running balance */}
                                    <div style={{ textAlign: 'right', minWidth: '80px' }}>
                                      <div style={{ fontSize: '0.56rem', color: '#9ca3af', textTransform: 'uppercase', fontWeight: 600 }}>Running</div>
                                      <div style={{ fontSize: '0.82rem', fontWeight: 800, color: isAdvance ? '#dc2626' : isPositive ? '#16a34a' : '#dc2626' }}>
                                        {row.running_balance >= 0 ? '+' : ''}₹{Number(row.running_balance).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                      </div>
                                      {row.can_pay && (
                                        <div style={{ fontSize: '0.58rem', color: '#b45309', fontWeight: 700 }}>⚡ PAY NOW</div>
                                      )}
                                    </div>
                                  </div>

                                  {/* Billing events inside this week */}
                                  {events.length > 0 && (
                                    <div style={{ padding: '6px 12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                      {events.map((ev: any, ei: number) => (
                                        <div key={ei} style={{
                                          background: ev.type === 'shoot_billing' ? '#f0fdf4' : ev.type === 'deposit_release' ? '#eff6ff' : '#f9fafb',
                                          border: `1px solid ${ev.type === 'shoot_billing' ? '#bbf7d0' : ev.type === 'deposit_release' ? '#bfdbfe' : '#e5e7eb'}`,
                                          borderRadius: '6px', padding: '6px 10px'
                                        }}>
                                          {/* Event header */}
                                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: ev.activities?.length > 0 ? '5px' : '0' }}>
                                            <div>
                                              <span style={{ fontSize: '0.64rem', fontWeight: 700, color: ev.type === 'shoot_billing' ? '#16a34a' : '#1d4ed8' }}>
                                                {ev.type === 'shoot_billing' ? '🌱 Shoot Selection Billed' : '✓ Deposit Released'}
                                              </span>
                                              <span style={{ fontSize: '0.62rem', color: '#6b7280', marginLeft: '6px' }}>{ev.farmer_name} · #{ev.job_id}</span>
                                            </div>
                                            <div style={{ textAlign: 'right' }}>
                                              <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#16a34a' }}>
                                                +₹{Number(ev.payable).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                              </div>
                                              {ev.deposit_held > 0 && (
                                                <div style={{ fontSize: '0.6rem', color: '#b45309' }}>
                                                  10% held ₹{Number(ev.deposit_held).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                                </div>
                                              )}
                                              {ev.deposit_released > 0 && (
                                                <div style={{ fontSize: '0.6rem', color: '#1d4ed8' }}>
                                                  ₹{Number(ev.deposit_released).toLocaleString('en-IN', { maximumFractionDigits: 0 })} released
                                                </div>
                                              )}
                                            </div>
                                          </div>

                                          {/* Activities table */}
                                          {ev.activities?.length > 0 && (
                                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.64rem' }}>
                                              <thead>
                                                <tr>
                                                  {['Activity', 'Area', 'Rate', 'Amount'].map(h => (
                                                    <th key={h} style={{ padding: '2px 4px', textAlign: ['Area','Rate','Amount'].includes(h) ? 'right' : 'left', color: '#9ca3af', fontWeight: 600, borderBottom: '1px solid #f3f4f6' }}>{h}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {ev.activities.map((act: any, ai: number) => (
                                                  <tr key={ai}>
                                                    <td style={{ padding: '2px 4px', color: '#374151' }}>{act.activity_name}</td>
                                                    <td style={{ padding: '2px 4px', textAlign: 'right', color: '#6b7280' }}>{Number(act.area).toFixed(2)}</td>
                                                    <td style={{ padding: '2px 4px', textAlign: 'right', color: '#6b7280' }}>₹{Number(act.rate).toLocaleString('en-IN')}</td>
                                                    <td style={{ padding: '2px 4px', textAlign: 'right', fontWeight: 700, color: '#0f766e' }}>₹{Number(act.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              );
                            })}

                            {/* Pending work — shoot selection not yet done */}
                            {pendingWork.length > 0 && (
                              <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', padding: '8px 12px' }}>
                                <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#b45309', textTransform: 'uppercase' }}>⏳ Work Done — Shoot Selection Pending</p>
                                {pendingWork.map((pw: any, pi: number) => (
                                  <div key={pi} style={{ marginBottom: pi < pendingWork.length - 1 ? '6px' : '0' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', marginBottom: '3px' }}>
                                      <span style={{ fontWeight: 700, color: '#374151' }}>{pw.farmer_name} · #{pw.job_id}</span>
                                      <span style={{ color: '#9ca3af' }}>₹{Number(pw.gross_so_far).toLocaleString('en-IN', { maximumFractionDigits: 0 })} earned (not yet payable)</span>
                                    </div>
                                    {pw.activities?.map((act: any, ai: number) => (
                                      <div key={ai} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.64rem', color: '#6b7280', paddingLeft: '8px' }}>
                                        <span>{act.activity_name}</span>
                                        <span>{Number(act.area).toFixed(2)} ac × ₹{Number(act.rate).toLocaleString('en-IN')} = ₹{Number(act.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                                      </div>
                                    ))}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })()}

                      {/* ── 3. TRANSACTION HISTORY TIMELINE ── */}
                      {(() => {
                        const txns: any[] = m.transaction_history || [];
                        if (txns.length === 0) return null;

                        const colorMap: any = {
                          advance:             { bg: '#fef2f2', border: '#fecaca', text: '#dc2626', icon: '💰' },
                          weekly:              { bg: '#fff7ed', border: '#fed7aa', text: '#ea580c', icon: '📅' },
                          settlement_payment:  { bg: '#f0fdf4', border: '#bbf7d0', text: '#16a34a', icon: '✅' },
                          misc_deduction:      { bg: '#faf5ff', border: '#e9d5ff', text: '#7c3aed', icon: '⚠️' },
                        };

                        return (
                          <div style={{ marginBottom: '4px' }}>
                            <p style={{ margin: '0 0 6px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>🧾 Transaction History</p>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {txns.map((txn: any, ti: number) => {
                                const c = colorMap[txn.type] || colorMap.weekly;
                                const isCredit = txn.amount > 0;
                                return (
                                  <div key={ti} style={{
                                    background: c.bg,
                                    border: `1px solid ${c.border}`,
                                    borderRadius: '8px',
                                    padding: '7px 12px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                  }}>
                                    {/* Icon + date */}
                                    <div style={{ minWidth: '56px', textAlign: 'center' }}>
                                      <div style={{ fontSize: '1rem' }}>{c.icon}</div>
                                      <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600 }}>{txn.date?.slice(5)}</div>
                                    </div>

                                    {/* Label + notes */}
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#1f2937', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                        {txn.label}
                                      </div>
                                      {txn.mode && txn.mode !== '—' && (
                                        <div style={{ fontSize: '0.6rem', color: '#6b7280' }}>
                                          {txn.mode}{txn.notes ? ` · ${txn.notes}` : ''}
                                        </div>
                                      )}
                                    </div>

                                    {/* Amount */}
                                    <div style={{ textAlign: 'right', minWidth: '80px' }}>
                                      <div style={{ fontSize: '0.82rem', fontWeight: 800, color: isCredit ? '#16a34a' : '#dc2626' }}>
                                        {isCredit ? '+' : ''}₹{Math.abs(txn.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                      </div>
                                      <div style={{ fontSize: '0.58rem', color: txn.running_balance >= 0 ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
                                        Bal: {txn.running_balance >= 0 ? '+' : ''}₹{txn.running_balance.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                      </div>
                                    </div>

                                    {/* Proof link */}
                                    {txn.proof_url && (
                                      <a href={txn.proof_url} target="_blank" rel="noreferrer"
                                        style={{ fontSize: '0.6rem', color: '#3b82f6', border: '1px solid #bfdbfe', borderRadius: '4px', padding: '2px 6px', background: '#eff6ff', whiteSpace: 'nowrap', textDecoration: 'none' }}>
                                        📎
                                      </a>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })()}

                      {/* ── 4. PER-JOB CARDS (gross + deposit status + activities) ── */}
                      <p style={{ margin: '4px 0 0', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>🌾 Job Details</p>
                      {m.settlements.length === 0 ? (
                        <p style={{ fontSize: '0.78rem', color: '#9ca3af', margin: 0 }}>No settlements yet</p>
                      ) : m.settlements.map((s: any) => {
                        const sm = STATUS_META[s.status] || STATUS_META.pending;
                        return (
                          <div key={s.job_id} style={{ background: '#fff', borderRadius: '10px', border: `1px solid ${s.status === 'calculated' ? '#fde68a' : s.status === 'paid' ? '#bbf7d0' : '#e5e7eb'}`, padding: '12px 14px' }}>
                            {/* Job header */}
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                              <div>
                                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#1d4ed8', fontSize: '0.8rem' }}>#{s.job_id}</span>
                                <span style={{ marginLeft: '8px', fontSize: '0.8rem', color: '#374151', fontWeight: 700 }}>{s.farmer_name}</span>
                                <div style={{ marginTop: '3px', display: 'flex', gap: '8px', flexWrap: 'wrap', fontSize: '0.66rem', color: '#6b7280' }}>
                                  <span>{s.job_title?.split('—')[0]?.trim()}</span>
                                </div>
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '3px' }}>
                                <span style={{ fontSize: '0.64rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: sm.bg, color: sm.text }}>{sm.label}</span>
                                {s.status === 'paid' && s.proof_url && (
                                  <a href={s.proof_url} target="_blank" rel="noreferrer"
                                    style={{ fontSize: '0.6rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0 5px', background: '#eff6ff' }}>📎 Payment proof</a>
                                )}
                              </div>
                            </div>

                            {/* Job gross + deposit pill */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', marginBottom: '10px' }}>
                              {[
                                { label: 'Gross Earned', val: `₹${Number(s.gross_amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e', bg: '#f0fdf4' },
                                { label: (() => { const acts = s.activities || []; const allDone = acts.length > 0 && acts.every((a: any) => a.work_status === 'completed'); return allDone ? '10% Released ✓' : '10% Held'; })(), val: `₹${Number(s.deposit_held).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: (() => { const acts = s.activities || []; return acts.length > 0 && acts.every((a: any) => a.work_status === 'completed') ? '#16a34a' : '#b45309'; })(), bg: (() => { const acts = s.activities || []; return acts.length > 0 && acts.every((a: any) => a.work_status === 'completed') ? '#f0fdf4' : '#fffbeb'; })() },
                                { label: '90% Payable', val: `₹${Number(s.payable_90pct).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#1d4ed8', bg: '#eff6ff' },
                              ].map((item, i) => (
                                <div key={i} style={{ background: item.bg, borderRadius: '6px', padding: '6px 8px', textAlign: 'center' }}>
                                  <div style={{ fontSize: '0.58rem', color: '#6b7280', marginBottom: '2px', fontWeight: 600 }}>{item.label}</div>
                                  <div style={{ fontSize: '0.8rem', fontWeight: 800, color: item.color }}>{item.val}</div>
                                </div>
                              ))}
                            </div>

                            {/* Activity table */}
                            <div style={{ border: '1px solid #e5e7eb', borderRadius: '7px', overflow: 'hidden', marginBottom: '8px' }}>
                              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.68rem' }}>
                                <thead>
                                  <tr style={{ background: '#f9fafb' }}>
                                    {['Activity', 'Plot', 'Date', 'Planned', 'Claimed', 'Crew', 'Rate', 'Earned', 'Status'].map(h => (
                                      <th key={h} style={{ padding: '4px 6px', textAlign: ['Planned','Claimed','Crew','Rate','Earned'].includes(h) ? 'right' : 'left', color: '#6b7280', fontWeight: 600, fontSize: '0.6rem', borderBottom: '1px solid #e5e7eb' }}>{h}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {s.activities.map((act: any, idx: number) => {
                                    const claimed  = act.mukkadam_claimed_area ?? act.actual_area_done;
                                    const billing  = act.admin_override_area ?? (act.use_actual_for_settlement && claimed != null ? claimed : act.allocated_area);
                                    const billAmt  = act.billing_locked ? 0 : billing * act.mukkadam_rate;
                                    const diff     = claimed != null ? (claimed - act.allocated_area) : 0;
                                    return (
                                      <tr key={idx} style={{ borderTop: idx > 0 ? '1px solid #f3f4f6' : 'none', background: act.billing_locked ? '#fff5f5' : 'transparent' }}>
                                        <td style={{ padding: '5px 6px', fontWeight: 600, color: '#111827' }}>
                                          {act.activity_name}
                                          {act.is_carry_forward && <span style={{ fontSize: '0.56rem', color: '#b45309', marginLeft: '2px' }}>↩</span>}
                                        </td>
                                        <td style={{ padding: '5px 6px', color: '#6b7280', fontFamily: 'monospace', fontSize: '0.62rem' }}>{act.plot_code}</td>
                                        <td style={{ padding: '5px 6px', color: '#6b7280', whiteSpace: 'nowrap' }}>{act.allocated_date?.slice(5) || act.scheduled_date?.slice(5) || '—'}</td>
                                        <td style={{ padding: '5px 6px', textAlign: 'right', color: '#6b7280' }}>{Number(act.allocated_area).toFixed(2)}</td>
                                        <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                                          {claimed != null ? (
                                            <span style={{ fontWeight: 700, color: diff < 0 ? '#dc2626' : diff > 0 ? '#0f766e' : '#374151' }}>
                                              {Number(claimed).toFixed(2)}
                                              {diff !== 0 && <span style={{ fontSize: '0.56rem', marginLeft: '2px' }}>({diff > 0 ? '+' : ''}{diff.toFixed(2)})</span>}
                                            </span>
                                          ) : <span style={{ color: '#9ca3af' }}>—</span>}
                                        </td>
                                        <td style={{ padding: '5px 6px', textAlign: 'right', color: '#6b7280' }}>{act.actual_crew_size ?? act.allocated_workers}</td>
                                        <td style={{ padding: '5px 6px', textAlign: 'right', color: '#6b7280' }}>₹{Number(act.mukkadam_rate).toLocaleString('en-IN')}</td>
                                        <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700, color: act.billing_locked ? '#9ca3af' : '#0f766e' }}>
                                          {act.billing_locked ? '🔒' : `₹${Number(billAmt).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
                                        </td>
                                        <td style={{ padding: '5px 6px' }}>
                                          <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', alignItems: 'center' }}>
                                            <WorkStatusBadge status={act.work_status || 'work_not_started'} />
                                            <PaymentStatusBadge status={act.payment_status || 'pending'} />
                                          </div>
                                        </td>
                                      </tr>
                                    );
                                  })}
                                  <tr style={{ borderTop: '2px solid #e5e7eb', background: '#f0fdfa' }}>
                                    <td colSpan={3} style={{ padding: '5px 6px', fontWeight: 700, fontSize: '0.68rem' }}>Total</td>
                                    <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700, color: '#6b7280' }}>
                                      {s.activities.reduce((t: number, a: any) => t + Number(a.allocated_area), 0).toFixed(2)}
                                    </td>
                                    <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700 }}>
                                      {s.activities.some((a: any) => (a.mukkadam_claimed_area ?? a.actual_area_done) != null)
                                        ? s.activities.reduce((t: number, a: any) => t + Number(a.mukkadam_claimed_area ?? a.actual_area_done ?? a.allocated_area), 0).toFixed(2)
                                        : '—'}
                                    </td>
                                    <td colSpan={2} />
                                    <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 800, color: '#0f766e' }}>
                                      ₹{s.gross_amount.toLocaleString('en-IN')}
                                    </td>
                                    <td />
                                  </tr>
                                </tbody>
                              </table>
                            </div>

                            {/* Misc costs per job */}
                            <MiscCostsSection
                              mukkadamId={m.mukkadam_id}
                              jobId={s.job_id}
                              initialCosts={s.misc_costs || []}
                              onCostChange={fetchData}
                            />

                            {s.status === 'paid' && (
                              <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px 14px', marginTop: '8px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <div>
                                    <div style={{ fontSize: '0.62rem', color: '#16a34a', fontWeight: 700, textTransform: 'uppercase', marginBottom: '2px' }}>✓ Settlement Paid</div>
                                    <div style={{ fontSize: '0.72rem', color: '#374151' }}>on {s.paid_at || '—'}</div>
                                  </div>
                                  <div style={{ textAlign: 'right' }}>
                                    <div style={{ fontSize: '1rem', fontWeight: 800, color: '#16a34a' }}>₹{Number(s.net_payable).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                                    {s.proof_url && (
                                      <a href={s.proof_url} target="_blank" rel="noreferrer"
                                        style={{ fontSize: '0.62rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '4px', padding: '1px 7px', background: '#eff6ff', display: 'inline-block', marginTop: '2px' }}>
                                        📎 View Proof
                                      </a>
                                    )}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}

                      {/* Weekly payment banner */}
                      {weeklyDueToday && (
                        <div style={{ background: '#fefce8', border: '1px solid #fde68a', borderRadius: 8, padding: '10px 12px' }}>
                          <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#92400e', textTransform: 'uppercase' }}>📅 Weekly Payment Due Today</p>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>₹{Number(weeklyPaymentAmount).toLocaleString('en-IN')}</span>
                              <span style={{ color: '#6b7280', fontSize: '0.7rem', marginLeft: 6 }}>{m.crew_size} workers · {weeklyPaymentDayLabel}</span>
                            </div>
                            <button onClick={() => handleAddWeeklyPayment(m.mukkadam_id, assignmentId, weeklyPaymentAmount, m.mukkadam_name)}
                              style={{ background: '#d97706', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', fontWeight: 700, cursor: 'pointer', fontSize: '0.74rem' }}>
                              + Add Payment
                            </button>
                          </div>
                        </div>
                      )}
                      {alreadyPaidToday && (
                        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '8px 12px', fontSize: '0.74rem', color: '#16a34a', fontWeight: 700 }}>
                          ✓ Weekly payment already added today
                        </div>
                      )}
                      {/* Missed weekly payments */}
{(m.missed_weekly_dates || []).length > 0 && (
  <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '10px 12px' }}>
    <p style={{ margin: '0 0 8px', fontSize: '0.64rem', fontWeight: 700, color: '#dc2626', textTransform: 'uppercase' }}>
      ⚠️ Missed Weekly Payments
    </p>
    {m.missed_weekly_dates.map((missedDate: string) => (
      <div key={missedDate} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: '0.82rem' }}>₹{Number(weeklyPaymentAmount).toLocaleString('en-IN')}</span>
          <span style={{ color: '#9ca3af', fontSize: '0.68rem', marginLeft: 6 }}>
            was due on {missedDate}
          </span>
          <span style={{ marginLeft: 6, fontSize: '0.6rem', padding: '1px 6px', borderRadius: '999px', background: '#fef2f2', color: '#dc2626', fontWeight: 700 }}>
            Late
          </span>
        </div>
        <button
          onClick={() => {
            setWeeklyModal({ mukkadamId: m.mukkadam_id, assignmentId: assignmentId, amount: weeklyPaymentAmount, name: m.mukkadam_name,paymentDate: missedDate  });
            // Override the payment date to missed date after modal opens
          }}
          style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: 6, padding: '5px 12px', fontWeight: 700, cursor: 'pointer', fontSize: '0.72rem' }}
        >
          Pay Now (Late)
        </button>
      </div>
    ))}
  </div>
)}
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
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
          onClick={() => { setPayModal(null); setProofFile(null); }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '420px', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 24px 60px rgba(0,0,0,0.25)' }}
            onClick={e => e.stopPropagation()}>

            {/* Header */}
            <div style={{ padding: '20px 24px 0' }}>
              <h3 style={{ margin: '0 0 2px', fontSize: '1rem', fontWeight: 700 }}>💰 Collect Payment</h3>
              <p style={{ margin: '0 0 16px', fontSize: '0.75rem', color: '#6b7280' }}>
                From <strong>{payModal.farmerName}</strong> · Job #{payModal.jobId}
              </p>
            </div>

            {/* Already Paid History */}
            {(payModal.existingPayments || []).filter((p: any) => p.type !== 'advance').length > 0 && (
              <div style={{ margin: '0 24px 14px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '10px 12px' }}>
                <p style={{ margin: '0 0 8px', fontSize: '0.62rem', fontWeight: 700, color: '#16a34a', textTransform: 'uppercase' }}>✓ Already Collected</p>
                {(payModal.existingPayments || []).filter((p: any) => p.type !== 'advance').map((p: any, i: number) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '6px', marginBottom: i < (payModal.existingPayments || []).filter((x:any)=>x.type!=='advance').length - 1 ? '6px' : 0, borderBottom: i < (payModal.existingPayments || []).filter((x:any)=>x.type!=='advance').length - 1 ? '1px solid #dcfce7' : 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px', background: '#dcfce7', color: '#16a34a', fontWeight: 600 }}>{p.mode}</span>
                      <span style={{ fontSize: '0.68rem', color: '#6b7280' }}>{p.date}</span>
                      {p.notes && <span style={{ fontSize: '0.62rem', color: '#9ca3af' }}>· {p.notes}</span>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontWeight: 700, color: '#16a34a', fontSize: '0.82rem' }}>₹{Number(p.amount).toLocaleString('en-IN')}</span>
                      {p.proof_url && (
                        <a href={p.proof_url} target="_blank" rel="noreferrer"
                          style={{ fontSize: '0.62rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '4px', padding: '1px 6px', background: '#eff6ff' }}>
                          📎 View
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* New Payment Form */}
            <div style={{ padding: '0 24px 20px' }}>
              <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Amount (₹)</label>
              <input type="number" value={payAmount} onChange={e => setPayAmount(e.target.value)}
                style={{ width: '100%', padding: '10px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '1.1rem', fontWeight: 700, marginBottom: '10px', boxSizing: 'border-box' }} />

              <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Payment Mode</label>
              <select value={payMode} onChange={e => setPayMode(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '10px', background: '#fff', boxSizing: 'border-box' }}>
                {['CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE'].map(m => (
                  <option key={m} value={m}>{m === 'ZOHO_PAYMENT' ? 'Zoho Payment' : m === 'BANK_TRANSFER' ? 'Bank Transfer' : m}</option>
                ))}
              </select>

              <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Notes (optional)</label>
              <input value={payNotes} onChange={e => setPayNotes(e.target.value)} placeholder="e.g. UPI ref 12345"
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '12px', boxSizing: 'border-box' }} />

              {/* Proof Upload — required */}
              <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
                Payment Proof <span style={{ color: '#dc2626', fontWeight: 700 }}>*</span>
                <span style={{ color: '#9ca3af', fontWeight: 400 }}> (screenshot / receipt / photo)</span>
              </label>
              {proofFile ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', border: '1.5px solid #bbf7d0', borderRadius: '8px', background: '#f0fdf4', marginBottom: '16px' }}>
                  {proofFile.type.startsWith('image/') && (
                    <img src={URL.createObjectURL(proofFile)} alt="proof"
                      style={{ width: '40px', height: '40px', objectFit: 'cover', borderRadius: '4px', border: '1px solid #e5e7eb' }} />
                  )}
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    <p style={{ margin: 0, fontSize: '0.74rem', fontWeight: 600, color: '#16a34a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>✓ {proofFile.name}</p>
                    <p style={{ margin: 0, fontSize: '0.62rem', color: '#9ca3af' }}>{(proofFile.size / 1024).toFixed(0)} KB</p>
                  </div>
                  <button onClick={() => setProofFile(null)}
                    style={{ border: 'none', background: 'none', color: '#dc2626', cursor: 'pointer', fontSize: '1rem', fontWeight: 700, padding: '0 4px' }}>✕</button>
                </div>
              ) : (
                <label style={{ display: 'block', padding: '14px', border: '1.5px dashed #d1d5db', borderRadius: '8px', textAlign: 'center', cursor: 'pointer', background: '#f9fafb', marginBottom: '16px' }}>
                  <input type="file" accept="image/*,application/pdf" onChange={e => setProofFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                  <p style={{ margin: '0 0 2px', fontSize: '0.8rem', color: '#374151' }}>📷 Tap to attach proof</p>
                  <p style={{ margin: 0, fontSize: '0.66rem', color: '#9ca3af' }}>UPI screenshot, cheque photo, bank receipt</p>
                </label>
              )}

              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={() => { setPayModal(null); setProofFile(null); }}
                  style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.82rem', cursor: 'pointer' }}>
                  Cancel
                </button>
                <button onClick={handleFarmerPay}
                  disabled={payLoading || proofUploading || !proofFile || !payAmount}
                  style={{ flex: 2, padding: '10px', borderRadius: '8px', border: 'none',
                    background: (!proofFile || !payAmount) ? '#d1d5db' : proofUploading ? '#fbbf24' : payLoading ? '#93c5fd' : '#3b82f6',
                    color: '#fff', fontWeight: 700, fontSize: '0.85rem',
                    cursor: (!proofFile || !payAmount || payLoading || proofUploading) ? 'not-allowed' : 'pointer' }}>
                  {proofUploading ? '⬆ Uploading proof...' : payLoading ? 'Recording...' : !proofFile ? 'Attach proof first' : `Record ₹${parseFloat(payAmount || '0').toLocaleString('en-IN')}`}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Mukkadam Settlement Pay Modal ── */}
      {mukkadamPayModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
          onClick={() => { setMukkadamPayModal(null); setMukkadamProofFile(null); }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '380px', boxShadow: '0 24px 60px rgba(0,0,0,0.25)', padding: '22px 24px' }}
            onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 2px', fontSize: '1rem', fontWeight: 700 }}>🏦 Pay Mukkadam</h3>
            <p style={{ margin: '0 0 16px', fontSize: '0.75rem', color: '#6b7280' }}>
              <strong>{mukkadamPayModal.name}</strong> · Job #{mukkadamPayModal.jobId} · ₹{mukkadamPayModal.amount.toLocaleString('en-IN')}
            </p>
            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px 12px', marginBottom: '14px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.65rem', color: '#6b7280', marginBottom: '2px' }}>NET PAYABLE</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f766e' }}>₹{mukkadamPayModal.amount.toLocaleString('en-IN')}</div>
            </div>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Payment Mode</label>
            <select value={mukkadamPayMode} onChange={e => setMukkadamPayMode(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '10px', background: '#fff', boxSizing: 'border-box' }}>
              {['CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE'].map(m => (
                <option key={m} value={m}>{m === 'ZOHO_PAYMENT' ? 'Zoho Payment' : m === 'BANK_TRANSFER' ? 'Bank Transfer' : m}</option>
              ))}
            </select>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Notes (optional)</label>
            <input value={mukkadamPayNotes} onChange={e => setMukkadamPayNotes(e.target.value)} placeholder="e.g. UPI ref 12345"
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '12px', boxSizing: 'border-box' }} />
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
              Payment Proof <span style={{ color: '#dc2626', fontWeight: 700 }}>*</span>
            </label>
            {mukkadamProofFile ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', border: '1.5px solid #bbf7d0', borderRadius: '8px', background: '#f0fdf4', marginBottom: '16px' }}>
                {mukkadamProofFile.type.startsWith('image/') && (
                  <img src={URL.createObjectURL(mukkadamProofFile)} alt="proof" style={{ width: '36px', height: '36px', objectFit: 'cover', borderRadius: '4px' }} />
                )}
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 600, color: '#16a34a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>✓ {mukkadamProofFile.name}</p>
                </div>
                <button onClick={() => setMukkadamProofFile(null)} style={{ border: 'none', background: 'none', color: '#dc2626', cursor: 'pointer', fontSize: '1rem', fontWeight: 700 }}>✕</button>
              </div>
            ) : (
              <label style={{ display: 'block', padding: '12px', border: '1.5px dashed #d1d5db', borderRadius: '8px', textAlign: 'center', cursor: 'pointer', background: '#f9fafb', marginBottom: '16px' }}>
                <input type="file" accept="image/*,application/pdf" onChange={e => setMukkadamProofFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                <p style={{ margin: '0 0 2px', fontSize: '0.78rem', color: '#374151' }}>📷 Attach payment proof</p>
                <p style={{ margin: 0, fontSize: '0.64rem', color: '#9ca3af' }}>Screenshot / receipt / photo</p>
              </label>
            )}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button onClick={() => { setMukkadamPayModal(null); setMukkadamProofFile(null); }}
                style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.82rem', cursor: 'pointer' }}>Cancel</button>
              <button onClick={submitMukkadamPay}
                disabled={mukkadamPayLoading || mukkadamProofUploading || !mukkadamProofFile}
                style={{ flex: 2, padding: '10px', borderRadius: '8px', border: 'none',
                  background: !mukkadamProofFile ? '#d1d5db' : mukkadamProofUploading ? '#fbbf24' : mukkadamPayLoading ? '#99f6e4' : '#14b8a6',
                  color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: (!mukkadamProofFile || mukkadamPayLoading || mukkadamProofUploading) ? 'not-allowed' : 'pointer' }}>
                {mukkadamProofUploading ? '⬆ Uploading...' : mukkadamPayLoading ? 'Processing...' : !mukkadamProofFile ? 'Attach proof first' : `✓ Confirm Pay ₹${mukkadamPayModal.amount.toLocaleString('en-IN')}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Weekly Payment Modal ── */}
      {weeklyModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
          onClick={() => { setWeeklyModal(null); setWeeklyProofFile(null); }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '380px', boxShadow: '0 24px 60px rgba(0,0,0,0.25)', padding: '22px 24px' }}
            onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 2px', fontSize: '1rem', fontWeight: 700 }}>📅 Weekly Payment</h3>
            <p style={{ margin: '0 0 16px', fontSize: '0.75rem', color: '#6b7280' }}>
              <strong>{weeklyModal.name}</strong> · Today {new Date().toLocaleDateString('en-IN')}
            </p>
            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', padding: '10px 12px', marginBottom: '14px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.65rem', color: '#6b7280', marginBottom: '2px' }}>WEEKLY AMOUNT</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#1d4ed8' }}>₹{weeklyModal.amount.toLocaleString('en-IN')}</div>
            </div>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Payment Mode</label>
            <select value={weeklyMode} onChange={e => setWeeklyMode(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '10px', background: '#fff', boxSizing: 'border-box' }}>
              {['CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE'].map(m => (
                <option key={m} value={m}>{m === 'ZOHO_PAYMENT' ? 'Zoho Payment' : m === 'BANK_TRANSFER' ? 'Bank Transfer' : m}</option>
              ))}
            </select>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Notes (optional)</label>
            <input value={weeklyNotes} onChange={e => setWeeklyNotes(e.target.value)} placeholder="e.g. Cash given on site"
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '12px', boxSizing: 'border-box' }} />
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
              Payment Proof <span style={{ color: '#dc2626', fontWeight: 700 }}>*</span>
            </label>
            {weeklyProofFile ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', border: '1.5px solid #bbf7d0', borderRadius: '8px', background: '#f0fdf4', marginBottom: '16px' }}>
                {weeklyProofFile.type.startsWith('image/') && (
                  <img src={URL.createObjectURL(weeklyProofFile)} alt="proof" style={{ width: '36px', height: '36px', objectFit: 'cover', borderRadius: '4px' }} />
                )}
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 600, color: '#16a34a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>✓ {weeklyProofFile.name}</p>
                </div>
                <button onClick={() => setWeeklyProofFile(null)} style={{ border: 'none', background: 'none', color: '#dc2626', cursor: 'pointer', fontSize: '1rem', fontWeight: 700 }}>✕</button>
              </div>
            ) : (
              <label style={{ display: 'block', padding: '12px', border: '1.5px dashed #d1d5db', borderRadius: '8px', textAlign: 'center', cursor: 'pointer', background: '#f9fafb', marginBottom: '16px' }}>
                <input type="file" accept="image/*,application/pdf" onChange={e => setWeeklyProofFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                <p style={{ margin: '0 0 2px', fontSize: '0.78rem', color: '#374151' }}>📷 Attach payment proof</p>
                <p style={{ margin: 0, fontSize: '0.64rem', color: '#9ca3af' }}>Screenshot / receipt / photo</p>
              </label>
            )}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button onClick={() => { setWeeklyModal(null); setWeeklyProofFile(null); }}
                style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.82rem', cursor: 'pointer' }}>Cancel</button>
              <button onClick={submitWeeklyPayment}
                disabled={weeklyPayLoading || weeklyProofUploading || !weeklyProofFile}
                style={{ flex: 2, padding: '10px', borderRadius: '8px', border: 'none',
                  background: !weeklyProofFile ? '#d1d5db' : weeklyProofUploading ? '#fbbf24' : weeklyPayLoading ? '#bfdbfe' : '#1d4ed8',
                  color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: (!weeklyProofFile || weeklyPayLoading || weeklyProofUploading) ? 'not-allowed' : 'pointer' }}>
                {weeklyProofUploading ? '⬆ Uploading...' : weeklyPayLoading ? 'Saving...' : !weeklyProofFile ? 'Attach proof first' : `✓ Record ₹${weeklyModal.amount.toLocaleString('en-IN')}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── MiscCostsSection with proof upload ──────────────────────────────────────
function MiscCostsSection({
  mukkadamId, jobId, initialCosts, onCostChange,
}: {
  mukkadamId: number; jobId: string; initialCosts: any[]; onCostChange: () => void;
}) {
  const [costs, setCosts] = useState<any[]>(initialCosts);
  const [adding, setAdding] = useState(false);
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [proofUploading, setProofUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const handleAdd = async () => {
    if (!amount || parseFloat(amount) <= 0) { alert('Enter valid amount'); return; }
    if (!reason.trim()) { alert('Reason is required'); return; }
    if (!proofFile) { alert('Proof is required'); return; }

    setProofUploading(true);
    let proofS3Key: string | null = null;
    try {
      // const { uploadFileToS3, getFileExtension } = await import('../utils/s3Upload');
      const userToken = localStorage.getItem('authToken') || localStorage.getItem('token') || '';
      const ext = getFileExtension(proofFile);
      const s3Name = `payments/misc/${mukkadamId}/job_${jobId}_${Date.now()}.${ext}`;
      proofS3Key = await uploadFileToS3(proofFile, s3Name, userToken);
      if (!proofS3Key) { alert('❌ Proof upload failed'); return; }
    } finally { setProofUploading(false); }

    setSaving(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamId}/job/${jobId}/misc/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount: parseFloat(amount), reason, proof_s3_key: proofS3Key }),
        }
      );
      const data = await res.json();
      if (res.ok) {
        setCosts(prev => [data, ...prev]);
        setAmount(''); setReason(''); setProofFile(null); setAdding(false);
        onCostChange();
      } else { alert(data.error); }
    } finally { setSaving(false); }
  };

  const handleDelete = async (costId: number) => {
    if (!confirm('Remove this misc cost?')) return;
    setDeletingId(costId);
    try {
      const res = await fetch(`${API_BASE_URL}/api/mukkadam/${mukkadamId}/job/${jobId}/misc/${costId}/`, { method: 'DELETE' });
      if (res.ok) { setCosts(prev => prev.filter(c => c.id !== costId)); onCostChange(); }
    } finally { setDeletingId(null); }
  };

  const total = costs.reduce((t, c) => t + Number(c.amount), 0);

  return (
    <div style={{ background: '#fafafa', borderRadius: '8px', border: '1px solid #e5e7eb', padding: '10px 12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <p style={{ margin: 0, fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>⚠ Misc Deductions</p>
        {!adding && (
          <button onClick={() => setAdding(true)}
            style={{ fontSize: '0.68rem', padding: '3px 10px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontWeight: 600, cursor: 'pointer' }}>
            + Add
          </button>
        )}
      </div>

      {adding && (
        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #fde68a', padding: '10px', marginBottom: '8px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px', marginBottom: '8px' }}>
            <div>
              <label style={{ fontSize: '0.65rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Amount (₹)</label>
              <input type="number" value={amount} onChange={e => setAmount(e.target.value)} placeholder="0"
                style={{ width: '100%', padding: '6px 8px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '0.82rem', fontWeight: 700, boxSizing: 'border-box' }} />
            </div>
            <div>
              <label style={{ fontSize: '0.65rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Reason <span style={{ color: '#ef4444' }}>*</span></label>
              <input type="text" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Tool damage, travel..."
                style={{ width: '100%', padding: '6px 8px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '0.78rem', boxSizing: 'border-box' }} />
            </div>
          </div>
          <label style={{ fontSize: '0.65rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
            Proof <span style={{ color: '#ef4444' }}>*</span>
          </label>
          {proofFile ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 8px', border: '1px solid #bbf7d0', borderRadius: '6px', background: '#f0fdf4', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.72rem', color: '#16a34a', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>✓ {proofFile.name}</span>
              <button onClick={() => setProofFile(null)} style={{ border: 'none', background: 'none', color: '#dc2626', cursor: 'pointer', fontWeight: 700 }}>✕</button>
            </div>
          ) : (
            <label style={{ display: 'block', padding: '8px', border: '1px dashed #d1d5db', borderRadius: '6px', textAlign: 'center', cursor: 'pointer', background: '#f9fafb', marginBottom: '8px' }}>
              <input type="file" accept="image/*,application/pdf" onChange={e => setProofFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
              <span style={{ fontSize: '0.7rem', color: '#6b7280' }}>📷 Attach proof</span>
            </label>
          )}
          <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
            <button onClick={() => { setAdding(false); setAmount(''); setReason(''); setProofFile(null); }}
              style={{ padding: '5px 12px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.72rem', cursor: 'pointer' }}>Cancel</button>
            <button onClick={handleAdd} disabled={saving || proofUploading || !proofFile}
              style={{ padding: '5px 12px', borderRadius: '6px', border: 'none',
                background: !proofFile ? '#d1d5db' : proofUploading ? '#fde68a' : saving ? '#fde68a' : '#f59e0b',
                color: !proofFile ? '#9ca3af' : '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: (!proofFile || saving || proofUploading) ? 'not-allowed' : 'pointer' }}>
              {proofUploading ? '⬆ Uploading...' : saving ? 'Saving...' : !proofFile ? 'Attach proof' : 'Add Deduction'}
            </button>
          </div>
        </div>
      )}

      {costs.length === 0 ? (
        <p style={{ fontSize: '0.72rem', color: '#9ca3af', margin: 0, textAlign: 'center', padding: '8px 0' }}>No misc deductions</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {costs.map((c) => (
            <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px', borderRadius: '6px', background: '#fff', border: '1px solid #f3f4f6', fontSize: '0.74rem' }}>
              <div style={{ flex: 1 }}>
                <span style={{ color: '#374151', fontWeight: 600 }}>{c.reason}</span>
                <span style={{ color: '#9ca3af', fontSize: '0.62rem', marginLeft: '6px' }}>{c.created_at?.slice(0, 10)}</span>
                {c.proof_url && (
                  <a href={c.proof_url} target="_blank" rel="noreferrer"
                    style={{ marginLeft: '6px', fontSize: '0.58rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0px 4px', background: '#eff6ff' }}>
                    📎
                  </a>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 800, color: '#dc2626' }}>−₹{Number(c.amount).toLocaleString('en-IN')}</span>
                <button onClick={() => handleDelete(c.id)} disabled={deletingId === c.id}
                  style={{ padding: '2px 6px', borderRadius: '4px', border: 'none', background: '#fef2f2', color: '#ef4444', fontSize: '0.65rem', cursor: 'pointer', fontWeight: 700 }}>
                  {deletingId === c.id ? '...' : '✕'}
                </button>
              </div>
            </div>
          ))}
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 8px', borderTop: '1.5px solid #e5e7eb', marginTop: '2px', fontSize: '0.74rem' }}>
            <span style={{ fontWeight: 700, color: '#374151' }}>Total Misc</span>
            <span style={{ fontWeight: 800, color: '#dc2626' }}>−₹{total.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
          </div>
        </div>
      )}
    </div>
  );
}

const FarmScheduler: React.FC<FarmSchedulerProps> = ({clusterId, onBackToClusters,onOpenDialpadWithNumber}) => {
  // State
  const [dialpadOpen, setDialpadOpen] = useState(false);
const [dialpadNumber, setDialpadNumber] = useState('');
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

// const setViewMode = (mode: 'jobs' | 'allocations' | 'both' | 'payments') => {
//   if (mode === 'both') {
//     setViewModes(['jobs', 'allocations']);
//   } else if (mode === 'payments') {
//     setViewModes(['payments']);
//   } else {
//     setViewModes([mode]);
//   }
// };

// const currentMode = viewModes.includes('payments')
//   ? 'payments'
//   : viewModes.includes('jobs') && viewModes.includes('allocations')
//   ? 'both'
//   : viewModes.includes('allocations')
//   ? 'allocations'
//   : 'jobs';

const VIEW_OPTIONS: { value: 'jobs' | 'allocations' | 'both' | 'payments'; label: string }[] = [
  { value: 'jobs',        label: 'AI' },
  { value: 'both', label: 'Allocations ' },
  // { value: 'both',        label: 'AI + Allocations' },
  { value: 'payments',    label: '💰 Payments' },
];

// const [viewModes, setViewModes] = useState<('jobs' | 'allocations' | 'potential' | 'payments')[]>(['jobs']);

const currentMode =
  viewModes.includes('payments')
    ? 'payments'
    : viewModes.includes('jobs') && viewModes.includes('allocations')
    ? 'both'
    : viewModes.includes('allocations')
    ? 'allocations'
    : 'jobs';

const setViewMode = (mode: 'jobs' | 'allocations' | 'both' | 'payments') => {
  if (mode === 'both') {
    setViewModes(['jobs', 'allocations']);
  } else if (mode === 'payments') {
    setViewModes(['payments']);
  } else {
    setViewModes([mode]);
  }
};
const selected = VIEW_OPTIONS.find(o => o.value === currentMode) ?? VIEW_OPTIONS[0];
const [modeDropdownOpen, setModeDropdownOpen] = useState(false);


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

{/* <div className="view-tabs">
  <button className={currentMode === 'jobs' ? 'tab active' : 'tab'} onClick={() => setViewMode('jobs')}>AI</button>
  <button className={currentMode === 'both' ? 'tab active' : 'tab'} onClick={() => setViewMode('both')}>Allocations</button>
   <button className={currentMode === 'both' ? 'tab active' : 'tab'} onClick={() => setViewMode('both')}>Both</button> 
   <button className={currentMode === 'payments' ? 'tab active' : 'tab'} onClick={() => setViewMode('payments')}>
    💰 Payments
  </button> 
</div> */}

<div className="relative inline-block text-left">
  <button
    type="button"
    onClick={() => setModeDropdownOpen(o => !o)}
    className="border rounded px-2 py-1 text-sm bg-white flex items-center gap-1"
  >
    <span className="text-xs text-black">
      {selected.label}
    </span>
    <span className="text-[10px] text-gray-500">▼</span>
  </button>

 {modeDropdownOpen && (
    <div className="absolute z-10 mt-1 w-44 bg-white border border-gray-200 rounded shadow">
      {VIEW_OPTIONS.map(opt => (
        <button
          key={opt.value}
          type="button"
          onClick={() => {
            setViewMode(opt.value);
            setModeDropdownOpen(false);
          }}
          className={`w-full text-left px-3 py-1 text-xs hover:bg-gray-50 ${
            currentMode === opt.value ? 'font-semibold text-blue-600' : 'text-gray-800'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )}
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

<Dialpad
  isOpen={dialpadOpen}
  number={dialpadNumber}
  onClose={() => setDialpadOpen(false)}
  onNumberChange={setDialpadNumber}
/>




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


// import React, { useState, useEffect, useRef } from 'react';

// // ── Types ──────────────────────────────────────────────────────────────────
// type WorkStatus    = 'work_not_started' | 'in_progress' | 'completed';
// type PaymentStatus = 'pending' | 'dispute' | 'done' | 'settled';

// interface AllocationItem {
//   allocation_id: number;
//   allocated_date: string;
//   allocated_workers: number;
//   allocated_area: number;
//   actual_area_done: number | null;
//   actual_crew_size: number | null;
//   actual_start_time: string | null;
//   actual_end_time: string | null;
//   report_submitted: boolean;
//   mukkadam_claimed_area: number | null;
//   admin_override_area: number | null;
//   work_status: WorkStatus;
//   payment_status: PaymentStatus;
//   farmer_agreed: boolean | null;
//   farmer_dispute_reason: string | null;
//   dispute_reason: string | null;
//   use_actual_for_settlement: boolean;
//   mukkadam_rate: number;
//   farmer_rate: number;
//   mukkadam_amount: number;
//   farmer_amount: number;
//   is_carry_forward: boolean;
// }

// interface ActivityGroup {
//   activity_id: number;
//   activity_name: string;
//   scheduled_date: string;
//   allocated_area: number;
//   allocations: AllocationItem[];
// }

// interface FarmerJob {
//   job_id: string;
//   crop_name: string;
//   variety: string;
//   plot_name: string;
//   job_status: string;
//   first_activity_date: string;
//   last_activity_date: string;
//   total_job_amount: number;
//   total_billable_so_far: number;
//   advance_paid: number;
//   additional_paid: number;
//   total_paid: number;
//   balance_due: number;
//   all_activities_past: boolean;
//   final_gap: number | null;
//   payment_history: PaymentRecord[];
//   activities: ActivityGroup[];
// }

// interface FarmerRow {
//   farmer_id: string;
//   farmer_name: string;
//   mobile_number: string;
//   total_acres: number;
//   jobs: FarmerJob[];
// }

// interface PaymentRecord {
//   type: string;
//   amount: number;
//   mode: string;
//   paid_at: string;
//   notes?: string;
// }

// interface WeeklyBreakdown {
//   payment_date: string;
//   amount: number;
//   crew_size: number;
// }

// interface MukkadamSettlement {
//   job_id: string;
//   job_title: string;
//   farmer_name: string;
//   gross_amount: number;
//   deposit_held: number;
//   payable_90pct: number;
//   deposit_carried_forward: number;
//   credit_carried_forward: number;
//   advance_deducted: number;
//   weekly_payments_deducted: number;
//   misc_costs: number;
//   net_payable: number;
//   status: 'pending' | 'calculated' | 'payment_raised' | 'paid' | 'no_payment_needed';
//   show_raise_payment: boolean;
//   activities: ActivityGroup[];
//   weekly_breakdown: WeeklyBreakdown[];
// }

// interface MukkadamRow {
//   mukkadam_id: string;
//   mukkadam_name: string;
//   mobile_numbers: string;
//   advance_amount: number;
//   transport_price: number;
//   weekly_payment_amount: number;
//   weekly_payment_day_label: string;
//   weekly_payment_day_value: number;
//   already_paid_today: boolean;
//   total_weekly_paid: number;
//   settlements: MukkadamSettlement[];
// }

// interface DashboardData {
//   farmers: FarmerRow[];
//   mukkadams: MukkadamRow[];
//   summary: {
//     total_farmer_due: number;
//     total_mukkadam_due: number;
//     farmer_count: number;
//     mukkadam_count: number;
//   };
// }

// // ── Status Badge ────────────────────────────────────────────────────────────
// const WorkStatusBadge: React.FC<{ status: WorkStatus }> = ({ status }) => {
//   const cfg: Record<WorkStatus, { label: string; cls: string }> = {
//     work_not_started: { label: 'Work Not Started', cls: 'bg-gray-100 text-gray-600' },
//     in_progress:      { label: 'In Progress',      cls: 'bg-blue-100 text-blue-700' },
//     completed:        { label: 'Completed',         cls: 'bg-green-100 text-green-700' },
//   };
//   const c = cfg[status] || { label: status, cls: 'bg-gray-100 text-gray-600' };
//   return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${c.cls}`}>{c.label}</span>;
// };

// const PaymentStatusBadge: React.FC<{ status: PaymentStatus }> = ({ status }) => {
//   const cfg: Record<PaymentStatus, { label: string; cls: string }> = {
//     pending:  { label: 'Payment Pending', cls: 'bg-gray-100 text-gray-500' },
//     dispute:  { label: 'Dispute',         cls: 'bg-red-100 text-red-700' },
//     done:     { label: 'Done',            cls: 'bg-emerald-100 text-emerald-700' },
//     settled:  { label: 'Settled',         cls: 'bg-purple-100 text-purple-700' },
//   };
//   const c = cfg[status] || { label: status, cls: 'bg-gray-100 text-gray-600' };
//   return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${c.cls}`}>{c.label}</span>;
// };

// // ── S3 Image Upload Hook ────────────────────────────────────────────────────
// const useProofUpload = () => {
//   const [uploading, setUploading] = useState(false);
//   const [uploaded, setUploaded]   = useState<{ key: string; url: string } | null>(null);
//   const [error, setError]         = useState('');

//   const upload = async (file: File, proofType: string, referenceId: number) => {
//     setUploading(true);
//     setError('');
//     try {
//       // 1) Get presigned URL
//       const presignRes = await fetch(`${API_BASE_URL}/api/payments/proof-presign/`, {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           file_name:    file.name,
//           proof_type:   proofType,
//           reference_id: referenceId,
//         }),
//       });
//       const presignData = await presignRes.json();
//       if (!presignRes.ok) throw new Error(presignData.error || 'Presign failed');

//       // 2) Upload to S3
//       const uploadRes = await fetch(presignData.presigned_url, {
//         method:  'PUT',
//         body:    file,
//         headers: { 'Content-Type': presignData.content_type },
//       });
//       if (!uploadRes.ok) throw new Error('S3 upload failed');

//       // 3) Save reference
//       const saveRes = await fetch(`${API_BASE_URL}/api/payments/save-proof/`, {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           proof_type:   proofType,
//           reference_id: referenceId,
//           s3_key:       presignData.s3_key,
//           file_name:    file.name,
//         }),
//       });
//       const saveData = await saveRes.json();
//       if (!saveRes.ok) throw new Error(saveData.error || 'Save failed');

//       setUploaded({ key: presignData.s3_key, url: saveData.s3_url });
//     } catch (e: any) {
//       setError(e.message || 'Upload failed');
//     } finally {
//       setUploading(false);
//     }
//   };

//   const reset = () => { setUploaded(null); setError(''); };
//   return { upload, uploading, uploaded, error, reset };
// };

// // ── Payment Modal (shared: farmer + mukkadam) ──────────────────────────────
// const PAYMENT_MODES = [
//   { value: 'CASH',          label: '💵 Cash' },
//   { value: 'UPI',           label: '📱 UPI' },
//   { value: 'BANK_TRANSFER', label: '🏦 Bank Transfer' },
//   { value: 'CHEQUE',        label: '📄 Cheque' },
//   { value: 'OTHER',         label: '⋯ Other' },
// ];

// interface PaymentModalProps {
//   title: string;
//   suggestedAmount: number;
//   proofType: 'farmer' | 'mukkadam' | 'weekly';
//   onPay: (amount: number, mode: string, notes: string, proofKey?: string) => Promise<void>;
//   onClose: () => void;
// }

// const PaymentModal: React.FC<PaymentModalProps> = ({
//   title, suggestedAmount, proofType, onPay, onClose
// }) => {
//   const [amount, setAmount]   = useState(suggestedAmount.toFixed(2));
//   const [mode, setMode]       = useState('CASH');
//   const [notes, setNotes]     = useState('');
//   const [saving, setSaving]   = useState(false);
//   const [error, setError]     = useState('');
//   const fileRef               = useRef<HTMLInputElement>(null);
//   const { upload, uploading, uploaded, error: uploadErr, reset: resetUpload } = useProofUpload();

//   const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
//     const file = e.target.files?.[0];
//     if (!file) return;
//     await upload(file, proofType, 0); // reference_id updated after payment saved
//   };

//   const handlePay = async () => {
//     const amt = parseFloat(amount);
//     if (!amt || amt <= 0) { setError('Enter valid amount'); return; }
//     if (!uploaded) { setError('Please upload payment proof'); return; }
//     setSaving(true);
//     setError('');
//     try {
//       await onPay(amt, mode, notes, uploaded.key);
//     } catch (e: any) {
//       setError(e.message || 'Payment failed');
//     } finally {
//       setSaving(false);
//     }
//   };

//   return (
//     <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
//       <div className="bg-white rounded-xl w-full max-w-md shadow-xl">
//         <div className="flex items-center justify-between p-4 border-b">
//           <h3 className="font-semibold text-gray-800">{title}</h3>
//           <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
//         </div>
//         <div className="p-4 space-y-4">
//           {/* Amount */}
//           <div>
//             <label className="block text-sm font-medium text-gray-700 mb-1">Amount (₹)</label>
//             <input
//               type="number"
//               value={amount}
//               onChange={e => setAmount(e.target.value)}
//               className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
//             />
//           </div>

//           {/* Payment Mode */}
//           <div>
//             <label className="block text-sm font-medium text-gray-700 mb-1">Payment Source</label>
//             <div className="grid grid-cols-3 gap-2">
//               {PAYMENT_MODES.map(m => (
//                 <button
//                   key={m.value}
//                   onClick={() => setMode(m.value)}
//                   className={`text-xs py-2 px-2 rounded-lg border transition-colors ${
//                     mode === m.value
//                       ? 'bg-blue-600 text-white border-blue-600'
//                       : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
//                   }`}
//                 >
//                   {m.label}
//                 </button>
//               ))}
//             </div>
//           </div>

//           {/* Notes */}
//           <div>
//             <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
//             <input
//               type="text"
//               value={notes}
//               onChange={e => setNotes(e.target.value)}
//               placeholder="Reference number, remarks..."
//               className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
//             />
//           </div>

//           {/* Proof Upload */}
//           <div>
//             <label className="block text-sm font-medium text-gray-700 mb-1">
//               Payment Proof <span className="text-red-500">*</span>
//             </label>
//             {uploaded ? (
//               <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg p-2">
//                 <span className="text-green-600 text-sm">✓ Uploaded: {uploaded.key.split('/').pop()}</span>
//                 <button
//                   onClick={() => { resetUpload(); if (fileRef.current) fileRef.current.value = ''; }}
//                   className="ml-auto text-xs text-red-500 hover:text-red-700"
//                 >
//                   Remove
//                 </button>
//               </div>
//             ) : (
//               <div
//                 onClick={() => fileRef.current?.click()}
//                 className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center cursor-pointer hover:border-blue-400 transition-colors"
//               >
//                 {uploading ? (
//                   <p className="text-sm text-blue-600">Uploading...</p>
//                 ) : (
//                   <>
//                     <p className="text-sm text-gray-500">📷 Tap to upload receipt / screenshot</p>
//                     <p className="text-xs text-gray-400 mt-1">JPG, PNG, PDF supported</p>
//                   </>
//                 )}
//                 <input
//                   ref={fileRef}
//                   type="file"
//                   accept="image/*,.pdf"
//                   className="hidden"
//                   onChange={handleFileChange}
//                 />
//               </div>
//             )}
//             {uploadErr && <p className="text-xs text-red-500 mt-1">{uploadErr}</p>}
//           </div>

//           {error && <p className="text-sm text-red-600 bg-red-50 rounded p-2">{error}</p>}
//         </div>

//         <div className="p-4 border-t flex gap-2">
//           <button
//             onClick={onClose}
//             className="flex-1 py-2.5 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
//           >
//             Cancel
//           </button>
//           <button
//             onClick={handlePay}
//             disabled={saving || uploading}
//             className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
//           >
//             {saving ? 'Processing...' : `Pay ₹${parseFloat(amount || '0').toLocaleString('en-IN')}`}
//           </button>
//         </div>
//       </div>
//     </div>
//   );
// };

// // ── Dispute Override Panel ─────────────────────────────────────────────────
// const DisputeOverridePanel: React.FC<{
//   alloc: AllocationItem;
//   onResolved: () => void;
// }> = ({ alloc, onResolved }) => {
//   const [area, setArea]     = useState('');
//   const [reason, setReason] = useState(alloc.dispute_reason || '');
//   const [saving, setSaving] = useState(false);
//   const [error, setError]   = useState('');

//   const handleSave = async () => {
//     if (!area) { setError('Enter area'); return; }
//     setSaving(true);
//     try {
//       const res = await fetch(`${API_BASE_URL}/api/attendance/resolve-dispute/`, {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           allocation_id:       alloc.allocation_id,
//           farmer_claimed_area: parseFloat(area),
//           dispute_reason:      reason,
//         }),
//       });
//       const data = await res.json();
//       if (!res.ok) throw new Error(data.error || 'Failed');
//       onResolved();
//     } catch (e: any) {
//       setError(e.message);
//     } finally {
//       setSaving(false);
//     }
//   };

//   return (
//     <div className="bg-red-50 border border-red-200 rounded-lg p-3 mt-2">
//       <p className="text-xs font-semibold text-red-700 mb-2">
//         🚨 Dispute — Fill farmer's claim after call
//       </p>
//       <div className="text-xs text-red-600 mb-2">
//         Mukkadam claimed: <strong>{alloc.mukkadam_claimed_area ?? alloc.actual_area_done} acres</strong>
//       </div>
//       <div className="flex gap-2 mb-2">
//         <input
//           type="number"
//           value={area}
//           onChange={e => setArea(e.target.value)}
//           placeholder="Farmer says (acres)"
//           className="flex-1 border border-red-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-red-400"
//         />
//       </div>
//       <textarea
//         value={reason}
//         onChange={e => setReason(e.target.value)}
//         placeholder="Reason (water logging, crop damage...)"
//         rows={2}
//         className="w-full border border-red-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-red-400 mb-2"
//       />
//       {error && <p className="text-xs text-red-700 mb-1">{error}</p>}
//       <button
//         onClick={handleSave}
//         disabled={saving}
//         className="w-full py-1.5 bg-red-600 text-white rounded text-xs font-medium hover:bg-red-700 disabled:opacity-50"
//       >
//         {saving ? 'Saving...' : 'Unlock Billing with This Area'}
//       </button>
//     </div>
//   );
// };

// // ── Allocation Row (shared) ────────────────────────────────────────────────
// const AllocationRow: React.FC<{
//   alloc: AllocationItem;
//   onDisputeResolved: () => void;
// }> = ({ alloc, onDisputeResolved }) => {
//   const [showDispute, setShowDispute] = useState(false);

//   const billingArea = alloc.admin_override_area ?? alloc.actual_area_done ?? alloc.allocated_area;

//   return (
//     <div className="border-l-2 border-gray-200 pl-3 py-2">
//       <div className="flex items-center justify-between mb-1">
//         <div className="flex items-center gap-2">
//           <span className="text-xs text-gray-500">{alloc.allocated_date}</span>
//           <WorkStatusBadge status={alloc.work_status} />
//           <PaymentStatusBadge status={alloc.payment_status} />
//           {alloc.is_carry_forward && (
//             <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">↩ Carry Forward</span>
//           )}
//         </div>
//         <span className="text-xs text-gray-400">{alloc.allocated_workers} workers</span>
//       </div>

//       {/* Area comparison */}
//       <div className="grid grid-cols-3 gap-2 text-xs mt-1">
//         <div className="bg-gray-50 rounded p-1.5 text-center">
//           <div className="text-gray-500">Planned</div>
//           <div className="font-semibold">{alloc.allocated_area} ac</div>
//         </div>
//         <div className="bg-blue-50 rounded p-1.5 text-center">
//           <div className="text-blue-500">Claimed</div>
//           <div className="font-semibold text-blue-700">
//             {alloc.mukkadam_claimed_area ?? '—'} {alloc.mukkadam_claimed_area ? 'ac' : ''}
//           </div>
//         </div>
//         <div className={`rounded p-1.5 text-center ${alloc.admin_override_area ? 'bg-orange-50' : 'bg-emerald-50'}`}>
//           <div className={alloc.admin_override_area ? 'text-orange-500' : 'text-emerald-500'}>
//             {alloc.admin_override_area ? 'Override' : 'Billing'}
//           </div>
//           <div className={`font-semibold ${alloc.admin_override_area ? 'text-orange-700' : 'text-emerald-700'}`}>
//             {billingArea} ac
//           </div>
//         </div>
//       </div>

//       {/* Dispute panel */}
//       {alloc.payment_status === 'dispute' && !alloc.use_actual_for_settlement && (
//         <div className="mt-2">
//           <button
//             onClick={() => setShowDispute(v => !v)}
//             className="text-xs text-red-600 hover:text-red-800 underline"
//           >
//             {showDispute ? 'Hide' : '+ Resolve dispute / enter farmer claim'}
//           </button>
//           {showDispute && (
//             <DisputeOverridePanel alloc={alloc} onResolved={onDisputeResolved} />
//           )}
//         </div>
//       )}
//       {alloc.payment_status === 'dispute' && alloc.use_actual_for_settlement && (
//         <div className="mt-1 text-xs text-orange-600 bg-orange-50 rounded px-2 py-1">
//           ⚠ Billing using override area ({alloc.admin_override_area} ac). {alloc.dispute_reason}
//         </div>
//       )}
//     </div>
//   );
// };

// // ── FARMER CARD ────────────────────────────────────────────────────────────
// const FarmerCard: React.FC<{
//   farmer: FarmerRow;
//   onReload: () => void;
// }> = ({ farmer, onReload }) => {
//   const [expanded, setExpanded]     = useState(false);
//   const [payModal, setPayModal]     = useState<{ job: FarmerJob } | null>(null);

//   const totalBalance = farmer.jobs.reduce((s, j) => s + j.balance_due, 0);
//   const totalAmount  = farmer.jobs.reduce((s, j) => s + j.total_job_amount, 0);
//   const dateRange    = farmer.jobs.length > 0
//     ? `${farmer.jobs[0].first_activity_date} → ${farmer.jobs[farmer.jobs.length - 1].last_activity_date}`
//     : '—';

//   const handleCollect = async (amount: number, mode: string, notes: string, proofKey?: string) => {
//     if (!payModal) return;
//     const res = await fetch(`${API_BASE_URL}/api/farmer/${farmer.farmer_id}/job/${payModal.job.job_id}/payment/`, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({ amount, mode, notes, proof_s3_key: proofKey }),
//     });
//     const data = await res.json();
//     if (!res.ok) throw new Error(data.error || 'Payment failed');
//     setPayModal(null);
//     onReload();
//   };

//   return (
//     <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
//       {/* ── COLLAPSED HEADER (always visible) ────────────────────────────── */}
//       <div
//         className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
//         onClick={() => setExpanded(v => !v)}
//       >
//         <div className="flex items-start justify-between">
//           <div>
//             <div className="flex items-center gap-2">
//               <span className="font-semibold text-gray-800">{farmer.farmer_name}</span>
//               <span className="text-xs text-gray-400">#{farmer.farmer_id}</span>
//             </div>
//             <div className="text-xs text-gray-500 mt-0.5">{farmer.mobile_number}</div>
//             <div className="text-xs text-gray-400 mt-0.5">📅 {dateRange}</div>
//             <div className="flex items-center gap-3 mt-1.5">
//               <span className="text-xs text-gray-500">
//                 Total: <strong className="text-gray-700">₹{totalAmount.toLocaleString('en-IN')}</strong>
//               </span>
//               <span className="text-xs text-gray-500">
//                 Acres: <strong className="text-gray-700">{farmer.total_acres}</strong>
//               </span>
//             </div>
//           </div>

//           {/* Balance + Collect Button */}
//           <div className="flex flex-col items-end gap-2" onClick={e => e.stopPropagation()}>
//             <div className="text-right">
//               <div className="text-xs text-gray-500">Balance Due</div>
//               <div className={`text-lg font-bold ${totalBalance > 0 ? 'text-red-600' : 'text-green-600'}`}>
//                 ₹{Math.abs(totalBalance).toLocaleString('en-IN')}
//               </div>
//             </div>
//             {farmer.jobs.map(job => (
//               job.balance_due > 0 && (
//                 <button
//                   key={job.job_id}
//                   onClick={() => setPayModal({ job })}
//                   className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
//                 >
//                   Collect ₹{job.balance_due.toLocaleString('en-IN')}
//                 </button>
//               )
//             ))}
//           </div>
//         </div>

//         {/* Jobs summary row */}
//         <div className="flex items-center gap-2 mt-2">
//           {farmer.jobs.map(job => (
//             <div key={job.job_id} className="flex items-center gap-1">
//               <span className="text-xs text-gray-500">{job.crop_name}</span>
//               {/* Work status count badges */}
//               {countWorkStatuses(job)}
//             </div>
//           ))}
//           <span className="ml-auto text-gray-400 text-xs">{expanded ? '▲' : '▼'} Details</span>
//         </div>
//       </div>

//       {/* ── EXPANDED DETAIL ───────────────────────────────────────────── */}
//       {expanded && (
//         <div className="border-t border-gray-100">
//           {farmer.jobs.map(job => (
//             <div key={job.job_id} className="p-4 border-b border-gray-50 last:border-0">
//               <div className="flex items-center justify-between mb-3">
//                 <div>
//                   <span className="font-medium text-gray-700">{job.crop_name}</span>
//                   {job.variety && <span className="text-xs text-gray-400 ml-1">({job.variety})</span>}
//                   <span className="text-xs text-gray-400 ml-2">{job.plot_name}</span>
//                 </div>
//                 <span className="text-xs text-gray-400">{job.job_id}</span>
//               </div>

//               {/* ── PAYMENT SECTION FIRST ─────────────────────────────── */}
//               <div className="bg-blue-50 rounded-xl p-3 mb-4">
//                 <div className="text-xs font-semibold text-blue-700 mb-2">💰 Payment Summary</div>
//                 <div className="grid grid-cols-2 gap-2 text-xs">
//                   <div>
//                     <div className="text-gray-500">Total Job Amount</div>
//                     <div className="font-semibold text-gray-800">₹{job.total_job_amount.toLocaleString('en-IN')}</div>
//                   </div>
//                   <div>
//                     <div className="text-gray-500">Billable So Far</div>
//                     <div className="font-semibold text-gray-800">₹{(job?.total_billable_so_far ?? 0).toLocaleString('en-IN')}</div>
//                   </div>
//                   <div>
//   <div className="text-gray-500">Advance Paid</div>
//   <div className="font-semibold text-green-700">
//     ₹{Number(job?.advance_paid ?? 0).toLocaleString('en-IN')}
//   </div>
// </div>

// <div>
//   <div className="text-gray-500">Additional Paid</div>
//   <div className="font-semibold text-green-700">
//     ₹{Number(job?.additional_paid ?? 0).toLocaleString('en-IN')}
//   </div>
// </div>

// <div className="col-span-2 pt-1 border-t border-blue-200">
//   <div className="text-gray-500">Balance Due</div>
//   <div
//     className={`text-lg font-bold ${
//       Number(job?.balance_due ?? 0) > 0
//         ? 'text-red-600'
//         : 'text-green-600'
//     }`}
//   >
//     ₹{Number(job?.balance_due ?? 0).toLocaleString('en-IN')}
//   </div>
// </div>
//                 </div>

//                 {/* Payment history */}
//                 {job.payment_history.length > 0 && (
//                   <div className="mt-2 pt-2 border-t border-blue-200">
//                     <div className="text-xs text-blue-600 font-medium mb-1">Payment History</div>
//                     {job.payment_history.map((p, i) => (
//                       <div key={i} className="flex items-center justify-between text-xs text-gray-600 py-0.5">
//                         <span>{p.type} — {p.mode}</span>
//                         <span className="font-medium text-green-700">₹{p.amount.toLocaleString('en-IN')}</span>
//                       </div>
//                     ))}
//                   </div>
//                 )}

//                 {job.balance_due > 0 && (
//                   <button
//                     onClick={() => setPayModal({ job })}
//                     className="mt-2 w-full py-2 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700"
//                   >
//                     Collect ₹{job.balance_due.toLocaleString('en-IN')}
//                   </button>
//                 )}
//               </div>

//               {/* ── ACTIVITIES ────────────────────────────────────────── */}
//               <div className="space-y-3">
//                 {job.activities.map(act => (
//                   <div key={act.activity_id} className="bg-gray-50 rounded-lg p-3">
//                     <div className="flex items-center justify-between mb-2">
//                       <span className="text-sm font-medium text-gray-700">{act.activity_name}</span>
//                       <span className="text-xs text-gray-400">{act.scheduled_date}</span>
//                     </div>
//                     <div className="space-y-2">
//                       {act.allocations.map(alloc => (
//                         <AllocationRow
//                           key={alloc.allocation_id}
//                           alloc={alloc}
//                           onDisputeResolved={onReload}
//                         />
//                       ))}
//                     </div>
//                   </div>
//                 ))}
//               </div>
//             </div>
//           ))}
//         </div>
//       )}

//       {/* Payment Modal */}
//       {payModal && (
//         <PaymentModal
//           title={`Collect from ${farmer.farmer_name} — ${payModal.job.crop_name}`}
//           suggestedAmount={payModal.job.balance_due}
//           proofType="farmer"
//           onPay={handleCollect}
//           onClose={() => setPayModal(null)}
//         />
//       )}
//     </div>
//   );
// };

// // Helper: count work statuses in a job for summary badges
// function countWorkStatuses(job: FarmerJob) {
//   const counts: Record<string, number> = {};
//   job.activities.forEach(act =>
//     act.allocations.forEach(a => {
//       counts[a.work_status] = (counts[a.work_status] || 0) + 1;
//     })
//   );
//   return (
//     <div className="flex gap-1">
//       {counts.work_not_started > 0 && (
//         <span className="text-xs bg-gray-100 text-gray-600 px-1.5 rounded">
//           {counts.work_not_started} not started
//         </span>
//       )}
//       {counts.in_progress > 0 && (
//         <span className="text-xs bg-blue-100 text-blue-700 px-1.5 rounded">
//           {counts.in_progress} in progress
//         </span>
//       )}
//       {counts.completed > 0 && (
//         <span className="text-xs bg-green-100 text-green-700 px-1.5 rounded">
//           {counts.completed} completed
//         </span>
//       )}
//     </div>
//   );
// }

// // ── MUKKADAM CARD ──────────────────────────────────────────────────────────
// const MukkadamCard: React.FC<{
//   mukkadam: MukkadamRow;
//   onReload: () => void;
// }> = ({ mukkadam, onReload }) => {
//   const [expanded, setExpanded]   = useState(false);
//   const [payModal, setPayModal]   = useState<{ settlement: MukkadamSettlement } | null>(null);
//   const [weeklyModal, setWeeklyModal] = useState(false);
//   const [weeklyDate, setWeeklyDate]   = useState(new Date().toISOString().split('T')[0]);
//   const [weeklyAmt, setWeeklyAmt]     = useState(String(mukkadam.weekly_payment_amount));
//   const [weeklySaving, setWeeklySaving] = useState(false);

//   const totalEarned  = mukkadam.settlements.reduce((s, st) => s + st.gross_amount, 0);
//   const totalDue     = mukkadam.settlements.filter(st => st.status === 'calculated')
//                          .reduce((s, st) => s + st.net_payable, 0);

//   const todayDay = new Date().getDay(); // 0=Sun 1=Mon ...
//   const isWeeklyDueToday = mukkadam.weekly_payment_day_value === todayDay && !mukkadam.already_paid_today;

//   const handlePay = async (amount: number, mode: string, notes: string, proofKey?: string) => {
//     if (!payModal) return;
//     const res = await fetch(`${API_BASE_URL}/api/mukkadam/${mukkadam.mukkadam_id}/settlement/${payModal.settlement.job_id}/pay/`, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({ amount, mode, notes, proof_s3_key: proofKey }),
//     });
//     const data = await res.json();
//     if (!res.ok) throw new Error(data.error || 'Payment failed');
//     setPayModal(null);
//     onReload();
//   };

//   const handleWeeklyPay = async () => {
//     setWeeklySaving(true);
//     try {
//       // Find assignment_id from any settlement
//       const res = await fetch(`${API_BASE_URL}/api/weekly-payment/add/`, {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           mukkadam_id:  mukkadam.mukkadam_id,
//           amount:       parseFloat(weeklyAmt),
//           payment_date: weeklyDate,
//         }),
//       });
//       const data = await res.json();
//       if (!res.ok) throw new Error(data.error || 'Failed');
//       setWeeklyModal(false);
//       onReload();
//     } catch (e: any) {
//       alert(e.message);
//     } finally {
//       setWeeklySaving(false);
//     }
//   };

//   return (
//     <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
//       {/* ── COLLAPSED HEADER ──────────────────────────────────────────── */}
//       <div
//         className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
//         onClick={() => setExpanded(v => !v)}
//       >
//         <div className="flex items-start justify-between">
//           <div>
//             <div className="flex items-center gap-2">
//               <span className="font-semibold text-gray-800">{mukkadam.mukkadam_name}</span>
//             </div>
//             <div className="text-xs text-gray-400 mt-0.5">{mukkadam.mobile_numbers}</div>

//             {/* Financial summary row */}
//             <div className="flex flex-wrap gap-3 mt-2">
//               <div className="text-xs">
//                 <span className="text-gray-500">Advance: </span>
//                 <span className="font-medium text-gray-700">₹{mukkadam.advance_amount.toLocaleString('en-IN')}</span>
//               </div>
//               <div className="text-xs">
//                 <span className="text-gray-500">Weekly Paid: </span>
//                 <span className="font-medium text-gray-700">₹{mukkadam.total_weekly_paid.toLocaleString('en-IN')}</span>
//               </div>
//               <div className="text-xs">
//                 <span className="text-gray-500">Transport: </span>
//                 <span className="font-medium text-gray-700">₹{mukkadam.transport_price.toLocaleString('en-IN')}</span>
//               </div>
//               <div className="text-xs">
//                 <span className="text-gray-500">Total Earned: </span>
//                 <span className="font-semibold text-green-700">₹{totalEarned.toLocaleString('en-IN')}</span>
//               </div>
//             </div>
//           </div>

//           {/* Net payable + pay button */}
//           <div className="flex flex-col items-end gap-2" onClick={e => e.stopPropagation()}>
//             <div className="text-right">
//               <div className="text-xs text-gray-500">Net Payable</div>
//               <div className={`text-lg font-bold ${totalDue > 0 ? 'text-green-700' : 'text-gray-500'}`}>
//                 ₹{totalDue.toLocaleString('en-IN')}
//               </div>
//             </div>
//             {mukkadam.settlements.filter(s => s.show_raise_payment).map(s => (
//               <button
//                 key={s.job_id}
//                 onClick={() => setPayModal({ settlement: s })}
//                 className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700"
//               >
//                 Pay ₹{s.net_payable.toLocaleString('en-IN')}
//               </button>
//             ))}
//             {isWeeklyDueToday && (
//               <button
//                 onClick={() => setWeeklyModal(true)}
//                 className="text-xs bg-amber-500 text-white px-3 py-1.5 rounded-lg hover:bg-amber-600"
//               >
//                 Weekly Due Today
//               </button>
//             )}
//           </div>
//         </div>
//         <div className="flex justify-end mt-1">
//           <span className="text-gray-400 text-xs">{expanded ? '▲' : '▼'} Details</span>
//         </div>
//       </div>

//       {/* ── EXPANDED DETAIL ───────────────────────────────────────────── */}
//       {expanded && (
//         <div className="border-t border-gray-100">
//           {mukkadam.settlements.map(settlement => (
//             <div key={settlement.job_id} className="p-4 border-b border-gray-50 last:border-0">
//               <div className="flex items-center justify-between mb-3">
//                 <div>
//                   <span className="font-medium text-gray-700">{settlement.job_title}</span>
//                   <span className="text-xs text-gray-400 ml-2">{settlement.farmer_name}</span>
//                 </div>
//                 <span className="text-xs text-gray-400">{settlement.job_id}</span>
//               </div>

//               {/* ── PAYMENT / SETTLEMENT SECTION FIRST ─────────────── */}
//               <div className="bg-green-50 rounded-xl p-3 mb-4">
//                 <div className="text-xs font-semibold text-green-700 mb-2">💳 Settlement Breakdown</div>
//                 <div className="space-y-1 text-xs">
//                   <div className="flex justify-between">
//                     <span className="text-gray-600">Gross (total work done)</span>
//                     <span className="font-medium">₹{settlement.gross_amount.toLocaleString('en-IN')}</span>
//                   </div>
//                   <div className="flex justify-between text-red-600">
//                     <span>− 10% Deposit held</span>
//                     <span>₹{settlement.deposit_held.toLocaleString('en-IN')}</span>
//                   </div>
//                   <div className="flex justify-between font-medium border-t border-green-200 pt-1">
//                     <span className="text-gray-700">90% Payable</span>
//                     <span>₹{settlement.payable_90pct.toLocaleString('en-IN')}</span>
//                   </div>
//                   {settlement.deposit_carried_forward > 0 && (
//                     <div className="flex justify-between text-green-600">
//                       <span>+ Deposit from prev job</span>
//                       <span>₹{settlement.deposit_carried_forward.toLocaleString('en-IN')}</span>
//                     </div>
//                   )}
//                   {settlement.credit_carried_forward > 0 && (
//                     <div className="flex justify-between text-green-600">
//                       <span>+ Credit from prev jobs</span>
//                       <span>₹{settlement.credit_carried_forward.toLocaleString('en-IN')}</span>
//                     </div>
//                   )}
//                   {settlement.advance_deducted > 0 && (
//                     <div className="flex justify-between text-red-600">
//                       <span>− Advance</span>
//                       <span>₹{settlement.advance_deducted.toLocaleString('en-IN')}</span>
//                     </div>
//                   )}
//                   {settlement.weekly_payments_deducted > 0 && (
//                     <>
//                       <div className="flex justify-between text-red-600">
//                         <span>− Weekly payments</span>
//                         <span>₹{settlement.weekly_payments_deducted.toLocaleString('en-IN')}</span>
//                       </div>
//                       {settlement.weekly_breakdown.map((w, i) => (
//                         <div key={i} className="flex justify-between text-gray-400 pl-3">
//                           <span>{w.payment_date} ({w.crew_size} crew)</span>
//                           <span>₹{w.amount.toLocaleString('en-IN')}</span>
//                         </div>
//                       ))}
//                     </>
//                   )}
//                   {settlement.misc_costs > 0 && (
//                     <div className="flex justify-between text-red-600">
//                       <span>− Misc costs</span>
//                       <span>₹{settlement.misc_costs.toLocaleString('en-IN')}</span>
//                     </div>
//                   )}
//                   <div className="flex justify-between font-bold text-sm border-t border-green-200 pt-1">
//                     <span className={settlement.net_payable > 0 ? 'text-green-700' : 'text-gray-600'}>
//                       Net Payable
//                     </span>
//                     <span className={settlement.net_payable > 0 ? 'text-green-700' : 'text-gray-500'}>
//                       ₹{settlement.net_payable.toLocaleString('en-IN')}
//                     </span>
//                   </div>
//                 </div>

//                 {settlement.show_raise_payment && (
//                   <button
//                     onClick={() => setPayModal({ settlement })}
//                     className="mt-3 w-full py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700"
//                   >
//                     Pay ₹{settlement.net_payable.toLocaleString('en-IN')}
//                   </button>
//                 )}
//                 {settlement.status === 'paid' && (
//                   <div className="mt-2 text-center text-xs text-green-700 font-medium">✓ Paid</div>
//                 )}
//                 {settlement.net_payable <= 0 && settlement.status === 'no_payment_needed' && (
//                   <div className="mt-2 text-center text-xs text-gray-500">
//                     In credit — will absorb into next job
//                   </div>
//                 )}
//               </div>

//               {/* ── ACTIVITIES ────────────────────────────────────────── */}
//               <div className="space-y-3">
//                 {settlement.activities.map(act => (
//                   <div key={act.activity_id} className="bg-gray-50 rounded-lg p-3">
//                     <div className="flex items-center justify-between mb-2">
//                       <span className="text-sm font-medium text-gray-700">{act.activity_name}</span>
//                       <span className="text-xs text-gray-400">{act.scheduled_date}</span>
//                     </div>
//                     <div className="space-y-2">
//                       {act.allocations.map(alloc => (
//                         <AllocationRow
//                           key={alloc.allocation_id}
//                           alloc={alloc}
//                           onDisputeResolved={onReload}
//                         />
//                       ))}
//                     </div>
//                   </div>
//                 ))}
//               </div>
//             </div>
//           ))}

//           {/* Weekly payment section */}
//           <div className="p-4 border-t border-gray-100">
//             <div className="flex items-center justify-between">
//               <div>
//                 <div className="text-sm font-medium text-gray-700">Weekly Payment</div>
//                 <div className="text-xs text-gray-500">
//                   Due every {mukkadam.weekly_payment_day_label} — ₹{mukkadam.weekly_payment_amount.toLocaleString('en-IN')}
//                 </div>
//               </div>
//               <button
//                 onClick={() => setWeeklyModal(true)}
//                 className="text-xs bg-amber-500 text-white px-3 py-1.5 rounded-lg hover:bg-amber-600"
//               >
//                 Add Weekly Payment
//               </button>
//             </div>
//           </div>
//         </div>
//       )}

//       {/* Payment Modal */}
//       {payModal && (
//         <PaymentModal
//           title={`Pay ${mukkadam.mukkadam_name} — ${payModal.settlement.job_title}`}
//           suggestedAmount={payModal.settlement.net_payable}
//           proofType="mukkadam"
//           onPay={handlePay}
//           onClose={() => setPayModal(null)}
//         />
//       )}

//       {/* Weekly Payment Modal */}
//       {weeklyModal && (
//         <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
//           <div className="bg-white rounded-xl w-full max-w-sm shadow-xl p-4">
//             <div className="flex items-center justify-between mb-4">
//               <h3 className="font-semibold">Add Weekly Payment</h3>
//               <button onClick={() => setWeeklyModal(false)} className="text-gray-400">✕</button>
//             </div>
//             <div className="space-y-3">
//               <div>
//                 <label className="text-sm text-gray-600">Date</label>
//                 <input
//                   type="date"
//                   value={weeklyDate}
//                   onChange={e => setWeeklyDate(e.target.value)}
//                   className="w-full border rounded-lg px-3 py-2 text-sm mt-1"
//                 />
//               </div>
//               <div>
//                 <label className="text-sm text-gray-600">Amount (₹)</label>
//                 <input
//                   type="number"
//                   value={weeklyAmt}
//                   onChange={e => setWeeklyAmt(e.target.value)}
//                   className="w-full border rounded-lg px-3 py-2 text-sm mt-1"
//                 />
//               </div>
//             </div>
//             <div className="flex gap-2 mt-4">
//               <button onClick={() => setWeeklyModal(false)} className="flex-1 py-2 border rounded-lg text-sm">Cancel</button>
//               <button
//                 onClick={handleWeeklyPay}
//                 disabled={weeklySaving}
//                 className="flex-1 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50"
//               >
//                 {weeklySaving ? 'Saving...' : 'Add Payment'}
//               </button>
//             </div>
//           </div>
//         </div>
//       )}
//     </div>
//   );
// };

// // ── MAIN DASHBOARD ─────────────────────────────────────────────────────────
// const PaymentDashboard: React.FC<{ clusterId: number }> = ({ clusterId }) => {
//   const [data, setData]         = useState<DashboardData | null>(null);
//   const [loading, setLoading]   = useState(true);
//   const [tab, setTab]           = useState<'farmers' | 'mukkadams'>('farmers');
//   const [search, setSearch]     = useState('');

//   const load = async () => {
//     setLoading(true);
//     try {
//       const res = await fetch(`${API_BASE_URL}/api/cluster/${clusterId}/payment-dashboard/`);
//       const d   = await res.json();
//       setData(d);
//     } catch (e) {
//       console.error(e);
//     } finally {
//       setLoading(false);
//     }
//   };

//   useEffect(() => { load(); }, [clusterId]);

//   if (loading) return (
//     <div className="flex items-center justify-center h-64">
//       <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full" />
//     </div>
//   );
//   if (!data) return <div className="text-center text-red-500 p-8">Failed to load</div>;

//   const filteredFarmers  = data.farmers.filter(f =>
//     !search || f.farmer_name.toLowerCase().includes(search.toLowerCase())
//   );
//   const filteredMukkadams = data.mukkadams.filter(m =>
//     !search || m.mukkadam_name.toLowerCase().includes(search.toLowerCase())
//   );

//   return (
//     <div className="bg-gray-50 min-h-screen">
//       {/* Summary Bar */}
//       <div className="bg-white border-b border-gray-200 px-4 py-3">
//         <div className="grid grid-cols-4 gap-4 max-w-4xl mx-auto">
//           <div className="text-center">
//             <div className="text-xs text-gray-500">Farmers</div>
//             <div className="font-bold text-gray-800">{data.summary?.farmer_count}</div>
//           </div>
//           <div className="text-center">
//             <div className="text-xs text-gray-500">Due from Farmers</div>
//             <div className="font-bold text-red-600">₹{data.summary?.total_farmer_due.toLocaleString('en-IN')}</div>
//           </div>
//           <div className="text-center">
//             <div className="text-xs text-gray-500">Mukkadams</div>
//             <div className="font-bold text-gray-800">{data.summary?.mukkadam_count}</div>
//           </div>
//           <div className="text-center">
//             <div className="text-xs text-gray-500">To Pay Mukkadams</div>
//             <div className="font-bold text-green-700">₹{data.summary?.total_mukkadam_due.toLocaleString('en-IN')}</div>
//           </div>
//         </div>
//       </div>

//       {/* Tabs + Search */}
//       <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-4 sticky top-0 z-10">
//         <div className="flex bg-gray-100 rounded-lg p-1">
//           <button
//             onClick={() => setTab('farmers')}
//             className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
//               tab === 'farmers' ? 'bg-white shadow text-blue-700' : 'text-gray-500 hover:text-gray-700'
//             }`}
//           >
//             Farmers ({data.farmers.length})
//           </button>
//           <button
//             onClick={() => setTab('mukkadams')}
//             className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
//               tab === 'mukkadams' ? 'bg-white shadow text-blue-700' : 'text-gray-500 hover:text-gray-700'
//             }`}
//           >
//             Mukkadams ({data.mukkadams.length})
//           </button>
//         </div>
//         <input
//           type="text"
//           placeholder="Search..."
//           value={search}
//           onChange={e => setSearch(e.target.value)}
//           className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
//         />
//         <button onClick={load} className="text-gray-400 hover:text-gray-600 text-lg" title="Refresh">⟳</button>
//       </div>

//       {/* Cards */}
//       <div className="p-4 space-y-3 max-w-4xl mx-auto">
//         {tab === 'farmers' ? (
//           filteredFarmers.length === 0
//             ? <div className="text-center text-gray-400 py-12">No farmers found</div>
//             : filteredFarmers.map(f => (
//                 <FarmerCard key={f.farmer_id} farmer={f} onReload={load} />
//               ))
//         ) : (
//           filteredMukkadams.length === 0
//             ? <div className="text-center text-gray-400 py-12">No mukkadams found</div>
//             : filteredMukkadams.map(m => (
//                 <MukkadamCard key={m.mukkadam_id} mukkadam={m} onReload={load} />
//               ))
//         )}
//       </div>
//     </div>
//   );
// };
