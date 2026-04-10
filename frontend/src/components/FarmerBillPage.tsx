// FarmerBillingPage.tsx
import React, { useEffect, useState } from 'react';
import { API_BASE_URL } from '@/types/config';
import { useSearchParams } from 'react-router-dom';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Alloc {
  allocation_id: number;
  allocated_date: string;
  allocated_area: number;
  actual_area_done: number | null;
  admin_override_area: number | null;
  mukkadam_claimed_area: number | null;
  actual_start_time: string | null;
  work_status: string;
  payment_status: string;
  report_submitted: boolean;
  farmer_agreed: boolean | null;
  rate_per_acre: number;
  farmer_amount: number;
}

interface Activity {
  activity_id: number;
  activity_name: string;
  plot_name: string;
  plot_code: string;
  allocated_area: number;
  total_area: number;
  rate_per_acre: number;
  scheduled_date: string;
  allocation_status: string;
  billable_amount: number;
  actual_area_done: number | null;
  farmer_agreed: boolean | null;
  report_submitted: boolean;
  allocations: Alloc[];
  job_id?: string;
  mukkadam_name?: string;
}

interface Job {
  job_id: string;
  crop_name: string;
  bill_sent_map: Record<string, BillLog>;
  variety: string;
  plot_name: string;
  mukkadam_name: string;
  mukkadam_mobile: string;
  activities: Activity[];
  payment_history: PayHist[];
  summary: {
    total_billable_so_far: number;
    total_paid: number;
    balance_due: number;
  };
  bill_sent?: boolean;
}

interface Farmer {
  farmer_id: string;
  farmer_name: string;
  mobile_number: string;
  jobs: Job[];
}

interface PayHist {
  date: string;
  amount: number;
  mode: string;
  notes: string;
  proof_url?: string;
  type?: string;
}

interface ActivityGroup {
  activityName: string;
  jobId: string;
  plots: Array<{
    plotName: string;
    plotCode: string;
    jobId: string;
    activityId: number;
    allocatedArea: number;
    totalArea: number;       // ← always has the area, even if not allocated yet
    displayArea: number;     // ← totalArea if available, else allocatedArea
    rate: number;
    isDone: boolean;
    billableAmount: number;
    isEstimate: boolean;   // true = not yet actual billing, shown as estimate
    doneDate: string | null;
    mukkadam: string;
  }>;
  totalPlots: number;
  donePlots: number;
  totalConfirmed: number;  // sum of billable (completed allocations only)
  totalEstimate: number;  
  allDone: boolean;
  totalBillable: number;
  totalArea: number;
  rate: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function initials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

const AVATAR_COLORS = [
  { bg: '#e8f0fe', color: '#2471a3' },
  { bg: '#fef3e2', color: '#d68910' },
  { bg: '#fde8e8', color: '#c0392b' },
  { bg: '#f5eef8', color: '#8e44ad' },
  { bg: '#e8f8f0', color: '#1e8449' },
  { bg: '#fef9e7', color: '#b7950b' },
];

function avatarColor(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = id.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export function groupActivitiesByName(jobs: Job[]): ActivityGroup[] {
  const flat: Array<Activity & { job_id: string; mukkadam_name: string }> = [];
  jobs.forEach(job => {
    (job.activities ?? []).forEach(act => {
      flat.push({ ...act, job_id: job.job_id, mukkadam_name: job.mukkadam_name });
    });
  });

  // ── PRE-PASS: sum total_area across ALL JA rows per (jobId, actName, plotName, plotCode) ──
  // A single plot can have multiple JA rows (e.g. 1.5ac completed + 7ac pending).
  // We must know the TRUE expected total before deduplication drops the pending rows.
  const plotTotalAreaMap = new Map<string, number>();
  const plotCompletedAreaMap = new Map<string, number>();
  const plotAllAllocsMap = new Map<string, Alloc[]>();

  flat.forEach(act => {
    if (Number(act.total_area ?? 0) <= 0) return;
    const key = `${act.job_id}__${act.activity_name}__${act.plot_name}__${act.plot_code}`;

    // Sum total_area across all JA rows for this plot+activity
    plotTotalAreaMap.set(key, (plotTotalAreaMap.get(key) ?? 0) + Number(act.total_area ?? 0));

    // Accumulate completed area across all JA rows
    const completedArea = (act.allocations ?? [])
      .filter(a => a.work_status === 'completed')
      .reduce((s, a) => s + Number(a.admin_override_area ?? a.actual_area_done ?? a.allocated_area ?? 0), 0);
    plotCompletedAreaMap.set(key, (plotCompletedAreaMap.get(key) ?? 0) + completedArea);

    // Accumulate all allocs for this plot
    const existing = plotAllAllocsMap.get(key) ?? [];
    plotAllAllocsMap.set(key, [...existing, ...(act.allocations ?? [])]);
  });

  // Sort so completed activities come before pending duplicates of the same plot
  flat.sort((a, b) => {
    const scoreA = a.allocations?.some(x => x.work_status === 'completed') ? 3
      : (a as any).allocation_count > 0 ? 2
      : a.allocation_status === 'fully_allocated' ? 1 : 0;
    const scoreB = b.allocations?.some(x => x.work_status === 'completed') ? 3
      : (b as any).allocation_count > 0 ? 2
      : b.allocation_status === 'fully_allocated' ? 1 : 0;
    return scoreB - scoreA;
  });

  const map = new Map<string, ActivityGroup>();

  flat.forEach(act => {
    const mapKey = `${act.job_id}__${act.activity_name}`;
    if (!map.has(mapKey)) {
      map.set(mapKey, {
        activityName: act.activity_name,
        jobId:        act.job_id,
        plots: [],
        totalPlots:    0,
        donePlots:     0,
        allDone:       false,
        totalBillable: 0,
        totalArea:     0,
        totalConfirmed: 0,
        totalEstimate:  0,
        rate: act.rate_per_acre,
      });
    }
    const group = map.get(mapKey)!;

    // Skip duplicate plot — already processed via pre-pass
    const alreadyExists = group.plots.some(
      p => p.plotName === act.plot_name && p.plotCode === act.plot_code
    );
    if (alreadyExists) return;

    // Skip zero-area rows (ghost/AI placeholder rows)
    // BUT only skip if this plot has NO real area in any JA row
    const plotKey = `${act.job_id}__${act.activity_name}__${act.plot_name}__${act.plot_code}`;
    const trueTotalArea = plotTotalAreaMap.get(plotKey) ?? 0;
    if (trueTotalArea <= 0) return;

    const rate  = Number(act.rate_per_acre ?? 0);
    const aArea = Number(act.allocated_area ?? 0);

    // ── Use PRE-SUMMED values — the only reliable source ─────────────────
    const totalCompletedArea = plotCompletedAreaMap.get(plotKey) ?? 0;
    const allAllocs          = plotAllAllocsMap.get(plotKey) ?? [];

    const AREA_TOLERANCE = 0.05;

    // isDone: completed area must cover the TRUE total (sum of all JA rows for this plot)
    const completedAreaCoversPlot = totalCompletedArea >= trueTotalArea - AREA_TOLERANCE;
    const allAllocsCompleted =
      allAllocs.length > 0 && allAllocs.every(a => a.work_status === 'completed');

    const isDone =
      completedAreaCoversPlot ||                  // primary: area math against true total
      (allAllocsCompleted && completedAreaCoversPlot) ||  // belt+suspenders
      act.allocation_status === 'completed';       // backend explicit override

    const apiBillable = Number(act.billable_amount ?? 0);
    const apiEstimate  = Number((act as any).estimated_amount ?? 0);

    // doneDate: latest completed allocation date across all JA rows for this plot
    const latestAlloc = allAllocs
      .filter(a => a.work_status === 'completed')
      .sort((a, b) => (b.allocated_date ?? '').localeCompare(a.allocated_date ?? ''))[0];
    const doneDate =
      latestAlloc?.allocated_date ??
      allAllocs[0]?.allocated_date ??
      act.scheduled_date ??
      null;

    const mukkadamName =
      (act as any).mukkadam_name ||
      allAllocs.find(a => (a as any).mukkadam_name)?.mukkadam_name ||
      '—';

    group.plots.push({
      plotName:      act.plot_name,
      plotCode:      act.plot_code,
      jobId:         act.job_id,
      activityId:    act.activity_id,
      allocatedArea: aArea,
      totalArea:     trueTotalArea,           // ← summed true total
      displayArea:   trueTotalArea,           // ← always use true total
      rate,
      isDone,
      billableAmount: apiBillable,
      isEstimate:     apiEstimate > 0,
      doneDate:       isDone ? doneDate : null,
      mukkadam:       mukkadamName,
    });

    group.totalPlots++;
    if (isDone) group.donePlots++;
    group.totalBillable  += apiBillable;
    group.totalConfirmed += apiBillable;
    group.totalEstimate  += apiEstimate;
    group.totalArea      += trueTotalArea;    // ← summed true total
  });

  map.forEach(g => {
    g.allDone = g.totalPlots > 0 && g.donePlots === g.totalPlots;
  });

  return Array.from(map.values()).sort((a, b) => {
    const scoreA = a.allDone ? 2 : a.donePlots > 0 ? 1 : 0;
    const scoreB = b.allDone ? 2 : b.donePlots > 0 ? 1 : 0;
    if (scoreA !== scoreB) return scoreB - scoreA;
    return a.activityName.localeCompare(b.activityName);
  });
}

// ─── Bill Modal ───────────────────────────────────────────────────────────────
function ActivityBillModal({
  farmer, jobs, group, allPayments, totalPaid, onClose, onSent,
}: {
  farmer: Farmer; jobs: Job[]; group: ActivityGroup;
  allPayments: PayHist[]; totalPaid: number;
  onClose: () => void; onSent: () => void;
}) {
  const billableNow = group.totalBillable;
  const [sendResult, setSendResult] = useState<{ success: boolean; detail?: string } | null>(null);

  const balanceDue  = billableNow - totalPaid;
  const [sending, setSending] = useState(false);
  const [sent, setSent]       = useState(false);

  const handleSend = async () => {
    setSending(true);
    try {
      const token = localStorage.getItem('auth_token');

      // ── job: find the job that owns this activity group ──────────────
      // Each plot in the group has a jobId — use the first one
      const ownerJobId = group.plots[0]?.jobId ?? jobs[0]?.job_id ?? '';
      const ownerJob   = jobs.find(j => j.job_id === ownerJobId) ?? jobs[0];

      // Plot names for this activity (shown in job.plot)
      const allPlots = [...new Set(group.plots.map(p => p.plotName || p.plotCode))].join(', ');

      // ── work_done: exact schema the backend expects ───────────────────
      // Fields stored: activity, date, acres_done, rate_per_acre, amount
      // We add plot_name so the webhook message can show it (backend passes it through via full_payload)
      const workDone = group.plots.map(p => ({
        activity:      group.activityName,
        plot_name:     p.plotName || p.plotCode,   // stored in full_payload
        date:          p.doneDate ?? '',
        acres_done:    Number(p.displayArea),
        rate_per_acre: Number(p.rate),
        amount:        Math.round(p.billableAmount),
      }));

      // ── mukkadam: from group plots (most accurate) ────────────────────
      const mukkadamFromPlot = group.plots.find(p => p.mukkadam && p.mukkadam !== '—')?.mukkadam ?? '';

      // ── Exact payload matching send_farmer_bill_to_webhook backend ────
      // Required fields: farmer, job, mukkadam, work_done, bill_summary
      const payload = {
        timestamp: new Date().toISOString(),

        // farmer — stored as farmer_id / farmer_name / farmer_phone
        farmer: {
          id:    String(farmer.farmer_id),
          name:  farmer.farmer_name,
          phone: farmer.mobile_number || '',
        },

        // job — stored as job_id / crop_name / plot_name in FarmerBillWebhookLog
        job: {
          id:   String(ownerJobId),
          crop: ownerJob?.crop_name ?? '',
          plot: allPlots,
        },

        // mukkadam — stored as mukkadam_name / mukkadam_mobile
        mukkadam: {
          name:   mukkadamFromPlot || ownerJob?.mukkadam_name || '',
          mobile: ownerJob?.mukkadam_mobile || '',
        },
        activity_name: group.activityName,

        // work_done — backend maps: activity/date/acres_done/rate_per_acre/amount
        work_done: workDone,

        // payment_history — backend maps: date/amount/mode/notes
        payment_history: allPayments.map(p => ({
          date:   p.date,
          amount: Number(p.amount),
          mode:   p.mode,
          notes:  p.notes || '',
        })),

        // bill_summary — stored as total_billed/total_paid/balance_due
        bill_summary: {
          total_billed:       Math.round(billableNow),
          // total_already_paid: Math.round(totalPaid),
          // balance_due_now:    Math.round(balanceDue),
          total_already_paid: 0,                        // ← was creditForThisBill
    balance_due_now:    Math.round(billableNow), 
          why_this_bill: [
            `${group.activityName}`,
            `${group.totalPlots} plot${group.totalPlots !== 1 ? 's' : ''}: ${allPlots}`,
            `${group.totalArea.toFixed(2)} ac × ₹${group.rate.toLocaleString('en-IN')}/ac`,
            `= ₹${Math.round(billableNow).toLocaleString('en-IN')}`,
            totalPaid > 0 ? `Already collected: ₹${Math.round(totalPaid).toLocaleString('en-IN')}` : null,
            balanceDue > 0.01 ? `Balance due: ₹${Math.round(balanceDue).toLocaleString('en-IN')}` : 'Balance: Clear',
          ].filter(Boolean).join(' | '),
        },
      };

      const res = await fetch(`${API_BASE_URL}/api/farmer-bill/send-webhook/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Token ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      const result = await res.json();

      if (!res.ok) {
        throw new Error(result.error || `HTTP ${res.status}`);
      }

      // ── Webhook fired but OPS returned an issue ──
      if (result.success && result.webhook_success === false) {
        // Bill was saved in DB but OPS rejected it
        const msg = result.detail || result.message || 'Bill sent but OPS reported an issue';
        alert(`⚠️ ${msg}`);
        // Still mark as sent since we saved it
        setSent(true);
        setSendResult({ success: result.webhook_success !== false, detail: result.detail });

        onSent();
        return;
      }

      // ── Already paid case ──
      if (result.detail && result.detail.toLowerCase().includes('already paid')) {
        alert(`ℹ️ ${result.detail}`);
        setSent(true);
        setSendResult({ success: result.webhook_success !== false, detail: result.detail });

        onSent();
        return;
      }

      if (result.success) {
        setSent(true);
        setSendResult({ success: result.webhook_success !== false, detail: result.detail });

        onSent();
      } else {
        throw new Error(result.error || result.message || 'Unknown error');
      }
    } catch (e: any) {
      alert(`❌ Failed to send bill: ${e.message}`);
    } finally {
      setSending(false);
    }
  };

  const mukkadamName = group.plots.find(p => p.mukkadam && p.mukkadam !== '—')?.mukkadam || '—';

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
      onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: 16, width: 640, maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,.2)' }}
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #eef0f4', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 3 }}>
              📄 Generate Bill — {group.activityName}
            </div>
            <div style={{ fontSize: 13, color: '#8892a4' }}>
              {farmer.farmer_name} · {mukkadamName !== '—' ? `Mukkadam: ${mukkadamName}` : 'No mukkadam assigned'}
            </div>
          </div>
          <button onClick={onClose} style={{ width: 32, height: 32, borderRadius: 8, border: 'none', background: '#f5f6f8', fontSize: 16, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
        </div>

        {/* Step indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '16px 24px', borderBottom: '1px solid #eef0f4', background: '#f8f9fb' }}>
          {[
            { label: 'Work Done',    done: true,  active: false },
            { label: 'Review Bill',  done: false, active: true  },
            { label: 'Send',         done: false, active: false },
          ].map((step, i) => (
            <React.Fragment key={i}>
              {i > 0 && <div style={{ width: 24, height: 2, background: i === 1 ? '#27ae60' : '#eef0f4' }} />}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, color: step.done ? '#27ae60' : step.active ? '#1a1a2e' : '#aaa' }}>
                <div style={{ width: 24, height: 24, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, background: step.done ? '#27ae60' : step.active ? '#1a1a2e' : '#eef0f4', color: (step.done || step.active) ? '#fff' : '#aaa' }}>
                  {step.done ? '✓' : i + 1}
                </div>
                {step.label}
              </div>
            </React.Fragment>
          ))}
        </div>

        {/* Info box */}
        <div style={{ margin: '16px 24px 0', background: '#f0f7ff', border: '1px solid #c5d9f0', borderRadius: 10, padding: '12px 16px', fontSize: 13, color: '#2471a3', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <span>ℹ️</span>
          <span>
            {group.activityName} is complete on all <b>{group.totalPlots} plots</b> for <b>{farmer.farmer_name}</b>.
            This bill consolidates all plots into one farmer-level invoice.
          </span>
        </div>

        <div style={{ padding: '16px 24px' }}>

          {/* Bill line items */}
          <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: '#8892a4', marginBottom: 10 }}>
            Bill Line Items
          </div>
          <div style={{ border: '1px solid #eef0f4', borderRadius: 10, padding: '14px', marginBottom: 16 }}>
            {/* Header row */}
            <div style={{ display: 'flex', alignItems: 'center', padding: '0 0 8px', borderBottom: '2px solid #eef0f4', fontSize: 12, fontWeight: 700, color: '#8892a4' }}>
              <div style={{ width: 110 }}>PLOT</div>
              <div style={{ flex: 1 }}>DATE · MUKKADAM</div>
              <div style={{ width: 70, textAlign: 'right' }}>ACRES</div>
              <div style={{ width: 90, textAlign: 'right' }}>AMOUNT</div>
            </div>
            {group.plots.map((p, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderBottom: i < group.plots.length - 1 ? '1px solid #f5f6f8' : 'none' }}>
                <div style={{ width: 110, fontSize: 13, fontWeight: 600, color: '#2471a3' }}>{p.plotName || p.plotCode}</div>
                <div style={{ flex: 1, fontSize: 12, color: '#666' }}>
                  {p.doneDate ? p.doneDate.slice(5) : '—'}
                  {p.mukkadam && p.mukkadam !== '—' ? ` · ${p.mukkadam}` : ''}
                </div>
                <div style={{ width: 70, textAlign: 'right', fontSize: 13, fontWeight: 600 }}>{p.displayArea.toFixed(2)} ac</div>
                <div style={{ width: 90, textAlign: 'right', fontSize: 14, fontWeight: 700 }}>₹{Math.round(p.billableAmount).toLocaleString('en-IN')}</div>
              </div>
            ))}
            {/* Total row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '14px 0', borderTop: '2px solid #1a1a2e', marginTop: 8, fontSize: 16, fontWeight: 800 }}>
              <span>Total — {group.totalPlots} plot{group.totalPlots !== 1 ? 's' : ''} · {group.totalArea.toFixed(2)} ac</span>
              <span>₹{Math.round(billableNow).toLocaleString('en-IN')}</span>
            </div>
          </div>

          {/* Payment history */}
          {allPayments.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: '#8892a4', marginBottom: 10 }}>
                Payment History
              </div>
              {allPayments.map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', padding: '8px 0', borderBottom: i < allPayments.length - 1 ? '1px solid #f8f9fb' : 'none', gap: 12 }}>
                  <div style={{ width: 28, height: 28, borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, flexShrink: 0, background: p.type === 'advance' ? '#fef3e2' : '#e8f8f0', color: p.type === 'advance' ? '#d68910' : '#1e8449' }}>
                    {p.mode === 'UPI' ? '💳' : p.mode === 'CHEQUE' ? '📋' : '💵'}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>
                      {p.type === 'advance' ? 'Advance' : p.mode === 'UPI' ? 'UPI Payment' : p.mode === 'CHEQUE' ? 'Cheque' : p.mode}
                    </div>
                    <div style={{ fontSize: 11, color: '#8892a4' }}>
                      {p.date}{p.notes ? ` · ${p.notes}` : ''}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 700, color: '#27ae60' }}>
                      +₹{Number(p.amount).toLocaleString('en-IN')}
                    </span>
                    {p.proof_url && (
                      <a href={p.proof_url} target="_blank" rel="noreferrer"
                        style={{ fontSize: 11, color: '#3b82f6', border: '1px solid #bfdbfe', borderRadius: 4, padding: '1px 6px', background: '#eff6ff', textDecoration: 'none' }}>
                        📎 View
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Reconciliation */}
          <div style={{ background: '#f8f9fb', borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: '#8892a4', marginBottom: 10 }}>
              Payment Reconciliation
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 13 }}>
              <span style={{ color: '#666' }}>Bill Amount</span>
              <span style={{ fontWeight: 600 }}>₹{Math.round(billableNow).toLocaleString('en-IN')}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 13 }}>
              <span style={{ color: '#666' }}>Already Collected</span>
              <span style={{ fontWeight: 600, color: '#27ae60' }}>−₹{Math.round(totalPaid).toLocaleString('en-IN')}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0 0', borderTop: '2px solid #ddd', marginTop: 6, fontSize: 15, fontWeight: 700 }}>
              <span>Balance Due</span>
              <span style={{ color: balanceDue > 0.01 ? '#e74c3c' : '#27ae60' }}>
                {balanceDue > 0.01
                  ? `₹${Math.round(balanceDue).toLocaleString('en-IN')}`
                  : balanceDue < -0.01
                  ? `✓ Clear (₹${Math.round(Math.abs(balanceDue)).toLocaleString('en-IN')} overpaid)`
                  : '✓ Clear'}
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid #eef0f4', display: 'flex', gap: 10, justifyContent: 'flex-end', alignItems: 'center' }}>
          <span style={{ flex: 1, fontSize: 12, color: '#999' }}>
            {balanceDue > 0.01
              ? `Farmer owes ₹${Math.round(balanceDue).toLocaleString('en-IN')} after adjusting collected payments`
              : balanceDue < -0.01
              ? `Farmer has overpaid ₹${Math.round(Math.abs(balanceDue)).toLocaleString('en-IN')} — will be adjusted in next bill`
              : 'All settled — farmer is clear'}
          </span>
          <button onClick={onClose} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #ddd', background: '#fff', color: '#555', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
          {sent ? (
  <div style={{
    padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 700,
    background: sendResult?.success === false ? '#fef3c7' : '#e8f8f0',
    color: sendResult?.success === false ? '#92400e' : '#27ae60',
  }}>
    {sendResult?.success === false ? `⚠️ ${sendResult.detail?.slice(0, 60) || 'Sent with warning'}` : '✅ Sent'}
  </div>) : (
            <button onClick={handleSend} disabled={sending} style={{ padding: '8px 18px', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 600, cursor: sending ? 'not-allowed' : 'pointer', background: sending ? '#aaa' : balanceDue > 0.01 ? '#1a1a2e' : '#27ae60', color: '#fff' }}>
              {sending ? 'Sending...' : balanceDue > 0.01 ? `✉️ Send Bill ₹${Math.round(balanceDue).toLocaleString('en-IN')} Due` : '✉️ Send Bill ₹0 Due'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


function ViewBillModal({
  log, group, onClose, onResend,
}: {
  log: BillLog;
  group: ActivityGroup;
  onClose: () => void;
  onResend: () => void;
}) {
  const payload    = log.full_payload ?? {};
  const workDone   = payload.work_done ?? [];
  const payments   = payload.payment_history ?? [];
  const bill       = payload.bill_summary ?? {};
  const sentAt     = log.sent_at ? new Date(log.sent_at) : null;
  const waSuccess  = log.webhook_status === 200;

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
      onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: 16, width: 600, maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,.2)' }}
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #eef0f4', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 3 }}>
              📋 Bill Review — {group.activityName}
            </div>
            <div style={{ fontSize: 13, color: '#8892a4' }}>
              Sent by {log.sent_by}
              {sentAt ? ` · ${sentAt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} at ${sentAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : ''}
            </div>
          </div>
          <button onClick={onClose} style={{ width: 32, height: 32, borderRadius: 8, border: 'none', background: '#f5f6f8', fontSize: 16, cursor: 'pointer' }}>✕</button>
        </div>

        {/* WhatsApp status banner */}
        <div style={{ margin: '16px 24px 0', padding: '12px 16px', borderRadius: 10, display: 'flex', alignItems: 'center', gap: 10, background: waSuccess ? '#e8f8f0' : '#fde8e8', border: `1px solid ${waSuccess ? '#c3e6cb' : '#f5c6cb'}` }}>
          <span style={{ fontSize: 20 }}>{waSuccess ? '✅' : '⚠️'}</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: waSuccess ? '#1e8449' : '#c0392b' }}>
              {waSuccess ? 'WhatsApp Delivered' : 'WhatsApp Delivery Failed'}
            </div>
            <div style={{ fontSize: 11, color: '#8892a4' }}>
              Status code: {log.webhook_status ?? '—'}
              {sentAt ? ` · Sent ${sentAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : ''}
            </div>
          </div>
        </div>

        <div style={{ padding: '16px 24px' }}>

          {/* Work done line items */}
          <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: '#8892a4', marginBottom: 10 }}>
            Work Done
          </div>
          <div style={{ border: '1px solid #eef0f4', borderRadius: 10, padding: 14, marginBottom: 16 }}>
            <div style={{ display: 'flex', padding: '0 0 8px', borderBottom: '2px solid #eef0f4', fontSize: 12, fontWeight: 700, color: '#8892a4' }}>
              <div style={{ width: 110 }}>PLOT</div>
              <div style={{ flex: 1 }}>DATE</div>
              <div style={{ width: 70, textAlign: 'right' }}>ACRES</div>
              <div style={{ width: 90, textAlign: 'right' }}>AMOUNT</div>
            </div>
            {workDone.map((w: any, i: number) => (
              <div key={i} style={{ display: 'flex', padding: '10px 0', borderBottom: i < workDone.length - 1 ? '1px solid #f5f6f8' : 'none' }}>
                <div style={{ width: 110, fontSize: 13, fontWeight: 600, color: '#2471a3' }}>{w.plot_name || w.activity}</div>
                <div style={{ flex: 1, fontSize: 12, color: '#666' }}>{w.date ? w.date.slice(5) : '—'}</div>
                <div style={{ width: 70, textAlign: 'right', fontSize: 13, fontWeight: 600 }}>{Number(w.acres_done).toFixed(2)} ac</div>
                <div style={{ width: 90, textAlign: 'right', fontSize: 14, fontWeight: 700 }}>₹{Number(w.amount).toLocaleString('en-IN')}</div>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '14px 0 0', borderTop: '2px solid #1a1a2e', marginTop: 8, fontSize: 15, fontWeight: 800 }}>
              <span>Total Billed</span>
              <span>₹{Number(bill.total_billed ?? 0).toLocaleString('en-IN')}</span>
            </div>
          </div>

          {/* Payment history */}
          {payments.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: '#8892a4', marginBottom: 10 }}>
                Payment History
              </div>
              {payments.map((p: any, i: number) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', padding: '8px 0', borderBottom: i < payments.length - 1 ? '1px solid #f8f9fb' : 'none', gap: 12 }}>
                  <div style={{ width: 28, height: 28, borderRadius: 7, background: '#e8f8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13 }}>
                    {p.mode === 'UPI' ? '💳' : '💵'}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{p.mode}</div>
                    <div style={{ fontSize: 11, color: '#8892a4' }}>{p.date}{p.notes ? ` · ${p.notes}` : ''}</div>
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#27ae60' }}>
                    +₹{Number(p.amount).toLocaleString('en-IN')}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Balance — use live log values, not snapshot payload */}
{(() => {
  const liveBilled  = Number(log.total_billed  ?? bill.total_billed  ?? 0);
  // const livePaid    = Number(log.total_paid    ?? bill.total_already_paid ?? 0);
  // const liveBalance = Number(log.balance_due   ?? bill.balance_due_now   ?? 0);
  const livePaid    = 0;           // ← ignore log.total_paid
const liveBalance = liveBilled;  // ← just show full billed amount
  return (
    <div style={{ background: '#f8f9fb', borderRadius: 10, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '6px 0' }}>
        <span style={{ color: '#666' }}>Total Billed</span>
        <span style={{ fontWeight: 600 }}>₹{Math.round(liveBilled).toLocaleString('en-IN')}</span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '6px 0' }}>
        <span style={{ color: '#666' }}>Already Collected</span>
        <span style={{ fontWeight: 600, color: '#27ae60' }}>−₹{Math.round(livePaid).toLocaleString('en-IN')}</span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0 0', borderTop: '2px solid #ddd', marginTop: 6, fontSize: 15, fontWeight: 700 }}>
        <span>Balance Due</span>
        <span style={{ color: liveBalance > 0.01 ? '#e74c3c' : '#27ae60' }}>
          {liveBalance > 0.01
            ? `₹${Math.round(liveBalance).toLocaleString('en-IN')}`
            : liveBalance < -0.01
            ? `✓ Clear (₹${Math.round(Math.abs(liveBalance)).toLocaleString('en-IN')} overpaid)`
            : '✓ Clear'}
        </span>
      </div>
    </div>
  );
})()}
        </div>

        {/* Footer */}
        {/* <div style={{ padding: '16px 24px', borderTop: '1px solid #eef0f4', display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #ddd', background: '#fff', color: '#555', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
            Close
          </button>
          <button onClick={onResend} style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: '#1a1a2e', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
            🔁 Resend Bill
          </button>
        </div> */}
      </div>
    </div>
  );
}



interface BillLog {
  sent: boolean;
  sent_at: string;
  sent_by: string;
  webhook_status: number | null;
  total_billed: number;
  total_paid: number;
  balance_due: number;
  full_payload: any;
}
export default function FarmerBillingPage({ 
  clusterId: propClusterId,
  embeddedFarmerId,
  embeddedJobId,
}: { 
  clusterId?: number;
  embeddedFarmerId?: string;
  embeddedJobId?: string;
}) {

  const [searchParams] = useSearchParams();

  // Use prop if provided, else fall back to URL param
  const clusterId = propClusterId ?? searchParams.get('cluster');

const [viewBillModal, setViewBillModal] = useState<{
  group: ActivityGroup;
  log: BillLog;
  jobs: Job[];
  allPayments: PayHist[];
  totalPaid: number;
  farmer: Farmer;
} | null>(null);
  const [data, setData]                 = useState<{ farmers: Farmer[] } | null>(null);
  const [loading, setLoading]           = useState(true);
  const [selectedFarmerId, setSelectedFarmerId] = useState<string | null>(null);
  const [search, setSearch]             = useState('');
  const [billModal, setBillModal]       = useState<{
    farmer: Farmer; jobs: Job[]; group: ActivityGroup; allPayments: PayHist[]; totalPaid: number;
  } | null>(null);


   useEffect(() => {
    if (embeddedFarmerId && data?.farmers) {
      const found = data.farmers.find(
        (f: any) => String(f.farmer_id) === String(embeddedFarmerId)
      );
      if (found) setSelectedFarmerId(found.farmer_id);
    }
  }, [embeddedFarmerId, data]);
  const fetchData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API_BASE_URL}/api/cluster/${clusterId}/payment-dashboard/`, {
        headers: { Authorization: `Token ${token}` },
      });
      const d = await res.json();
      setData(d);
      if (d.farmers?.length > 0 && !selectedFarmerId) {
        setSelectedFarmerId(d.farmers[0].farmer_id);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [clusterId]);

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: '#9ca3af', fontSize: 14, fontFamily: 'Inter, -apple-system, sans-serif' }}>
      Loading billing data...
    </div>
  );
  if (!data) return null;

  const farmers       = data.farmers ?? [];
  const filteredFarmers = search.trim()
    ? farmers.filter(f => f.farmer_name.toLowerCase().includes(search.toLowerCase()))
    : farmers;
  const selectedFarmer = farmers.find(f => f.farmer_id === selectedFarmerId) ?? farmers[0] ?? null;
// Sort farmers: ready-to-bill unsent → ready-to-bill sent → others
const sortedFarmers = [...filteredFarmers].sort((a, b) => {
  const getScore = (f: Farmer) => {
    const groups = groupActivitiesByName(f.jobs ?? []);
    const readyGroups = groups.filter(g => g.allDone);
    if (readyGroups.length === 0) return 0;
    
    // Check if any ready group has bill NOT sent
    const allJobs = f.jobs ?? [];
    const hasUnsentBill = readyGroups.some(g => {
      const billLog = allJobs
        .flatMap(j => Object.entries(j.bill_sent_map ?? {}))
        .find(([actName]) => actName === g.activityName)?.[1];
      return !billLog;
    });
    
    return hasUnsentBill ? 2 : 1; // 2 = unsent ready, 1 = sent ready, 0 = others
  };
  return getScore(b) - getScore(a);
});
  return (
    <div style={{ display: 'flex', height: '100%', background: '#f0f2f5', fontFamily: "'Inter', -apple-system, sans-serif", fontSize: 14, color: '#1a1a2e', overflow: 'hidden' }}>

      {/* ══════════════════════════════════════════════
          SIDEBAR
      ══════════════════════════════════════════════ */}
      <div style={{  flexShrink: 0, background: '#fff', borderRight: '1px solid #e8ecf1', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Sidebar tabs
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #e8ecf1', display: 'flex', gap: 4 }}>
          <button style={{ padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer', background: '#1a1a2e', color: '#fff' }}>
            Farmers
          </button>
          <button style={{ padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer', background: '#e8ecf1', color: '#666' }}>
            Mukkadams
          </button>
        </div> */}
{/* Cluster stats — sticky */}
{data && (() => {
  const allFarmers   = data.farmers ?? [];
  const totalFarmers = allFarmers.length;
  const totalDueAll  = allFarmers.reduce((s, f) =>
    s + (f.jobs ?? []).reduce((js, j) => js + (j.summary?.balance_due ?? 0), 0), 0);
  const totalBilledAll = allFarmers.reduce((s, f) =>
    s + (f.jobs ?? []).reduce((js, j) => js + (j.summary?.total_billable_so_far ?? 0), 0), 0);
  const totalPaidAll = allFarmers.reduce((s, f) =>
    s + (f.jobs ?? []).reduce((js, j) => js + (j.summary?.total_paid ?? 0), 0), 0);
  const readyTobillAll = allFarmers.reduce((s, f) => {
    const groups = groupActivitiesByName(f.jobs ?? []);
    return s + groups.filter(g => g.allDone).length;
  }, 0);
  const unsentAll = allFarmers.reduce((s, f) => {
    const groups  = groupActivitiesByName(f.jobs ?? []);
    const allJobs = f.jobs ?? [];
    return s + groups.filter(g => g.allDone).filter(g => {
      const billLog = allJobs
        .flatMap(j => Object.entries(j.bill_sent_map ?? {}))
        .find(([actName]) => actName === g.activityName)?.[1];
      return !billLog;
    }).length;
  }, 0);

  return (
    <div style={{ padding: '10px 12px', borderBottom: '1px solid #e8ecf1', background: '#f8f9fb' }}>
      {/* Row 1 */}
      {/* <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
        <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: '6px 10px', border: '1px solid #eef0f4' }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: '#1a1a2e' }}>{totalFarmers}</div>
          <div style={{ fontSize: 9, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.5px' }}>Farmers</div>
        </div>
        <div style={{ flex: 1, background: unsentAll > 0 ? '#e8f8f0' : '#fff', borderRadius: 8, padding: '6px 10px', border: `1px solid ${unsentAll > 0 ? '#c3e6cb' : '#eef0f4'}` }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: unsentAll > 0 ? '#1e8449' : '#1a1a2e' }}>{unsentAll}</div>
          <div style={{ fontSize: 9, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.5px' }}>Bills Pending</div>
        </div>
        <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: '6px 10px', border: '1px solid #eef0f4' }}>
  <div style={{ fontSize: 15, fontWeight: 800, color: '#2471a3' }}>
    {allFarmers.reduce((s, f) => {
      const groups  = groupActivitiesByName(f.jobs ?? []);
      const allJobs = f.jobs ?? [];
      return s + groups.filter(g => g.allDone).filter(g => {
        const billLog = allJobs
          .flatMap(j => Object.entries(j.bill_sent_map ?? {}))
          .find(([actName]) => actName === g.activityName)?.[1];
        return !!billLog;
      }).length;
    }, 0)}
  </div>
  <div style={{ fontSize: 9, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.5px' }}>Bills Sent</div>
</div>
      </div>

      <div style={{ display: 'flex', gap: 6 }}>
        <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: '6px 10px', border: '1px solid #eef0f4' }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: '#e74c3c' }}>₹{Math.round(totalDueAll / 1000)}k</div>
          <div style={{ fontSize: 9, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.5px' }}>Due</div>
        </div>
        <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: '6px 10px', border: '1px solid #eef0f4' }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: '#3498db' }}>₹{Math.round(totalBilledAll / 1000)}k</div>
          <div style={{ fontSize: 9, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.5px' }}>Billed</div>
        </div>
        <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: '6px 10px', border: '1px solid #eef0f4' }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: '#27ae60' }}>₹{Math.round(totalPaidAll / 1000)}k</div>
          <div style={{ fontSize: 9, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.5px' }}>Collected</div>
        </div>
      </div> */}
    </div>
  );
})()}
        {/* Search */}
        {/* <div style={{ padding: '8px 16px', borderBottom: '1px solid #e8ecf1' }}>
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search farmers..."
            style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 12, fontFamily: 'inherit', boxSizing: 'border-box' }}
          />
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
          {sortedFarmers.map(f => {
  const avc        = avatarColor(f.farmer_id);
  
  const groups     = groupActivitiesByName(f.jobs ?? []);
  const readyGroups = groups.filter(g => g.allDone);
  const allJobs    = f.jobs ?? [];

  // Split ready groups into unsent vs sent
  const unsentReady = readyGroups.filter(g => {
    const billLog = allJobs
      .flatMap(j => Object.entries(j.bill_sent_map ?? {}))
      .find(([actName]) => actName === g.activityName)?.[1];
    return !billLog;
  });
  const sentReady = readyGroups.filter(g => {
    const billLog = allJobs
      .flatMap(j => Object.entries(j.bill_sent_map ?? {}))
      .find(([actName]) => actName === g.activityName)?.[1];
    return !!billLog;
  });

  const totalAc  = allJobs.reduce((s, j) =>
    s + (j.activities ?? []).reduce((a, act) => a + Number(act.total_area ?? 0), 0), 0);
  const isActive = f.farmer_id === selectedFarmerId;
const totalDue          = (f.jobs ?? []).reduce((s, j) => s + (j.summary?.balance_due ?? 0), 0);
const totalBilledFarmer = (f.jobs ?? []).reduce((s, j) => s + (j.summary?.total_billable_so_far ?? 0), 0); // ← ADD
  return (
    <div key={f.farmer_id} onClick={() => setSelectedFarmerId(f.farmer_id)}
      style={{
        padding: '10px 12px', borderRadius: 10, cursor: 'pointer',
        marginBottom: 2, transition: 'background .15s',
        background: isActive ? '#e8f0fe' : 'transparent',
        border: isActive ? '1px solid #c5d9f0' : '1px solid transparent',
      }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          fontWeight: 700, fontSize: 13, flexShrink: 0,
          background: avc.bg, color: avc.color,
        }}>
          {initials(f.farmer_name)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {f.farmer_name}
          </div>
          <div style={{ fontSize: 11, color: '#8892a4', marginTop: 1 }}>
            {allJobs.length} job{allJobs.length !== 1 ? 's' : ''} · {totalAc.toFixed(1)} ac
          </div>
        </div>
       {totalDue > 0.01 ? (
  <span style={{ fontSize: 11, fontWeight: 700, color: '#e74c3c', background: '#fde8e8', padding: '2px 6px', borderRadius: 5, flexShrink: 0 }}>
    ₹{Math.round(totalDue).toLocaleString('en-IN')}
  </span>
) : totalBilledFarmer > 0 ? (
  <span style={{ fontSize: 11, fontWeight: 700, color: '#2471a3', background: '#e8f0fe', padding: '2px 6px', borderRadius: 5, flexShrink: 0 }}>
    ₹{Math.round(totalBilledFarmer).toLocaleString('en-IN')}
  </span>
) : null}
      </div>


      <div style={{ marginTop: 5, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {unsentReady.length > 0 && (
          <div style={{
            fontSize: 10, fontWeight: 700, color: '#1e8449',
            background: '#e8f8f0', border: '1px solid #c3e6cb',
            padding: '2px 7px', borderRadius: 5,
          }}>
            🔔 {unsentReady.length} bill{unsentReady.length > 1 ? 's' : ''} pending
          </div>
        )}
        {sentReady.length > 0 && (
          <div style={{
            fontSize: 10, fontWeight: 700, color: '#2471a3',
            background: '#e8f0fe', border: '1px solid #c5d9f0',
            padding: '2px 7px', borderRadius: 5,
          }}>
            ✅ {sentReady.length} bill{sentReady.length > 1 ? 's' : ''} sent
          </div>
        )}
      </div>
    </div>
  );
})}
        </div> */}
      </div>

      {/* ══════════════════════════════════════════════
          MAIN CONTENT
      ══════════════════════════════════════════════ */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {!selectedFarmer ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: '#9ca3af', fontSize: 14 }}>Select a farmer</div>
        ) : (() => {
          const jobs = (selectedFarmer.jobs ?? []).filter(j =>
            !embeddedJobId || String(j.job_id) === String(embeddedJobId)
          );
          const groups       = groupActivitiesByName(jobs);
          const readyGroups  = groups.filter(g => g.allDone);
          // ── Use API summary — matches PaymentDashboard exactly ──────────
          // total_billable_so_far = sum of act_billable for past/agreed activities
          // total_paid            = sum of confirmed FarmerPayments
          // balance_due           = total_billable - total_paid (handles advances)
          const totalBilled  = jobs.reduce((s, j) => s + (j.summary?.total_billable_so_far ?? 0), 0);
          const totalPaid    = jobs.reduce((s, j) => s + (j.summary?.total_paid ?? 0), 0);
          const balanceDue   = jobs.reduce((s, j) => s + (j.summary?.balance_due ?? 0), 0);
          const allPayments  = jobs.flatMap(j => j.payment_history ?? []);
          const totalArea    = jobs.reduce((s, j) =>
            s + (j.activities ?? []).reduce((a, act) => a + Number(act.total_area ?? 0), 0), 0);
          const avc          = avatarColor(selectedFarmer.farmer_id);
          

          return (
            <>
              {/* ── TOP BAR ── */}
              <div style={{ background: '#fff', borderBottom: '1px solid #e8ecf1', padding: '16px 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 18, background: avc.bg, color: avc.color, flexShrink: 0 }}>
                    {initials(selectedFarmer.farmer_name)}
                  </div>
                  <div>
                    <div style={{ fontSize: 17, fontWeight: 700 }}>{selectedFarmer.farmer_name}</div>
                    <div style={{ fontSize: 12, color: '#8892a4', marginTop: 2 }}>
                      📞 {selectedFarmer.mobile_number || '—'}
                      {' · '}
                      {jobs.length} job{jobs.length !== 1 ? 's' : ''}
                      {' · '}
                      {totalArea.toFixed(1)} ac
                      {readyGroups.length > 0 && (
                        <span style={{ marginLeft: 8, color: '#1e8449', fontWeight: 600 }}>
                          · {readyGroups.length} activit{readyGroups.length > 1 ? 'ies' : 'y'} ready to bill
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Top bar stats */}
                {/* <div style={{ display: 'flex', gap: 12 }}>
                  {[
                    { label: 'Total Job Value', val: `₹${Math.round(jobs.reduce((s,j)=>s+(j.total_job_amount??0),0)).toLocaleString('en-IN')}`, bg: '#f8f9fb', color: '#1a1a2e' },
                    { label: 'Billed',          val: `₹${Math.round(totalBilled).toLocaleString('en-IN')}`,  bg: '#e8f0fe', color: '#2471a3' },
                    { label: 'Collected',       val: `₹${Math.round(totalPaid).toLocaleString('en-IN')}`,    bg: '#e8f8f0', color: '#27ae60' },
                    {
                      label: 'Balance',
                      val: balanceDue > 0.01 ? `₹${Math.round(balanceDue).toLocaleString('en-IN')}` : '✓ Clear',
                      bg: balanceDue > 0.01 ? '#fde8e8' : '#e8f8f0',
                      color: balanceDue > 0.01 ? '#e74c3c' : '#27ae60',
                    },
                  ].map((s, i) => (
                    <div key={i} style={{ textAlign: 'center', padding: '6px 16px', borderRadius: 8, background: s.bg }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: s.color }}>{s.val}</div>
                      <div style={{ fontSize: 10, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.5px' }}>{s.label}</div>
                    </div>
                  ))}
                </div> */}
              </div>

              {/* ── SCROLLABLE CONTENT ── */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px' }}>

                {/* Info box */}
                <div style={{ background: '#f0f7ff', border: '1px solid #c5d9f0', borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 13, color: '#2471a3', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>💡</span>
                  <span>Bills are generated <b>per activity</b> once work is complete across all plots. One consolidated bill per activity.</span>
                </div>

                {/* Section label */}
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: '#8892a4', marginBottom: 12 }}>
                  Activities · Billing Status
                </div>

                {/* ── Activity cards ── */}
                {groups.map(group => {
                  const pct = group.totalPlots > 0 ? Math.round((group.donePlots / group.totalPlots) * 100) : 0;
                  const progColor = group.allDone ? '#27ae60' : pct >= 50 ? '#f39c12' : '#e74c3c';

                  return (
                    <div key={group.activityName} style={{ background: '#fff', borderRadius: 14, marginBottom: 16, overflow: 'hidden', border: '1px solid #eef0f4', transition: 'box-shadow .2s' }}>

                      {/* Card header */}
                      <div style={{ padding: '18px 22px', display: 'flex', alignItems: 'center', gap: 16 }}>
                        {/* Icon */}
                        <div style={{ width: 42, height: 42, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0, background: group.allDone ? '#e8f8f0' : pct > 0 ? '#fef3e2' : '#f5f6f8' }}>
                          {group.allDone ? '✅' : pct > 0 ? '⏳' : '○'}
                        </div>

                        {/* Title */}
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 15, fontWeight: 700 }}>{group.activityName}</div>
                          <div style={{ fontSize: 12, color: '#8892a4', marginTop: 2 }}>
                            ₹{group.rate.toLocaleString('en-IN')}/ac
                            {group.plots[0]?.mukkadam && group.plots[0].mukkadam !== '—'
                              ? ` · Mukkadam: ${group.plots[0].mukkadam}`
                              : ' · Mukkadam: Not assigned'}
                          </div>
                        </div>

                        {/* Stats */}
                        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: 15, fontWeight: 700 }}>{group.totalArea.toFixed(2)} ac</div>
                            <div style={{ fontSize: 10, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.4px' }}>Total Area</div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: 15, fontWeight: 700, color: group.allDone ? '#27ae60' : pct >= 50 ? '#f39c12' : '#e74c3c' }}>
                              {group.donePlots}/{group.totalPlots}
                            </div>
                            <div style={{ fontSize: 10, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.4px' }}>Plots Done</div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
  {group.totalConfirmed > 0 && group.totalEstimate > 0 ? (
    // Mixed: some done, some pending
    <>
      <div style={{ fontSize: 15, fontWeight: 700, color: '#1a1a2e' }}>
        ₹{Math.round(group.totalConfirmed).toLocaleString('en-IN')}
        <span style={{ fontSize: 11, fontWeight: 500, color: '#d68910', marginLeft: 4 }}>
          +₹{Math.round(group.totalEstimate).toLocaleString('en-IN')} est.
        </span>
      </div>
      <div style={{ fontSize: 10, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.4px' }}>
        Confirmed + Estimate
      </div>
    </>
  ) : group.allDone ? (
    // All confirmed
    <>
      <div style={{ fontSize: 15, fontWeight: 700, color: '#2471a3' }}>
        ₹{Math.round(group.totalConfirmed).toLocaleString('en-IN')}
      </div>
      <div style={{ fontSize: 10, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.4px' }}>
        Bill Amount
      </div>
    </>
  ) : (
    // Nothing done yet — full estimate
    <>
      <div style={{ fontSize: 15, fontWeight: 700, color: '#d68910' }}>
        ₹{Math.round(group.totalEstimate).toLocaleString('en-IN')}
      </div>
      <div style={{ fontSize: 10, color: '#8892a4', textTransform: 'uppercase', letterSpacing: '.4px' }}>
        Est. Amount
      </div>
    </>
  )}
</div>
                        </div>
                      </div>

                      {/* Progress bar */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 22px 16px' }}>
                        <div style={{ flex: 1, height: 8, background: '#eef0f4', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{ height: '100%', borderRadius: 4, width: `${pct}%`, background: progColor, transition: 'width .4s ease' }} />
                        </div>
                        <div style={{ fontSize: 12, fontWeight: 700, minWidth: 44, color: progColor }}>{pct}%</div>
                      </div>

                      {/* Plot chips */}
                      <div style={{ padding: '0 22px 16px', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {group.plots.map((p, i) => (
                          <div key={i} style={{
                            padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                            display: 'flex', alignItems: 'center', gap: 6,
                            background: p.isDone ? '#e8f8f0' : '#f5f6f8',
                            border: `1px solid ${p.isDone ? '#c3e6cb' : '#e0e3e8'}`,
                            color: p.isDone ? '#1e8449' : '#888',
                          }}>
                            <span style={{ fontWeight: 800 }}>{p.isDone ? '✓' : '○'}</span>
                            {p.plotName || p.plotCode}
                            {` · ${p.displayArea.toFixed(2)} ac`}
                          </div>
                        ))}
                      </div>

                      {/* Bill status bar */}
                      <div style={{ padding: '14px 22px', borderTop: '1px solid #eef0f4', display: 'flex', alignItems: 'center', gap: 14 }}>
                        {group.allDone ? (() => {
  // Scope to this group's specific job only
  const groupJob    = jobs.find(j => j.job_id === group.jobId) ?? jobs[0];
  const billSentMap = groupJob?.bill_sent_map ?? {};
  const billLog     = billSentMap[group.activityName];

  return billLog ? (
    // ── Already sent ──
    <>
      <span style={{ padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: 700, background: '#e8f8f0', color: '#1e8449' }}>
        ✅ Bill Sent
      </span>
      <span style={{ fontSize: 12, color: '#8892a4', flex: 1 }}>
        Sent by <b style={{ color: '#1a1a2e' }}>{billLog.sent_by}</b>
        {billLog.sent_at ? ` · ${new Date(billLog.sent_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}` : ''}
        {' · '}
        <b style={{ color: billLog.balance_due > 0.01 ? '#e74c3c' : '#27ae60' }}>
          {billLog.balance_due > 0.01 ? `₹${Math.round(billLog.balance_due).toLocaleString('en-IN')} due` : '✓ Clear'}
        </b>
      </span>
      <button
        onClick={() => {
          const jobPayments  = groupJob?.payment_history ?? [];
          const jobTotalPaid = groupJob?.summary?.total_paid ?? 0;
          setViewBillModal({
            group,
            log:         billLog,
            jobs:        [groupJob],
            allPayments: jobPayments,
            totalPaid:   jobTotalPaid,
            farmer:      selectedFarmer,
          });
        }}
        style={{ padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 600, border: '1px solid #c5d9f0', cursor: 'pointer', background: '#e8f0fe', color: '#2471a3' }}
      >
        📋 View Bill
      </button>
    </>
  ) : (
    // ── Ready to send ──
    <>
      <span style={{ padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: 700, background: '#e8f8f0', color: '#1e8449' }}>
        ✓ Ready to Bill
      </span>
      <span style={{ fontSize: 12, color: '#8892a4', flex: 1 }}>
        All {group.totalPlots} plot{group.totalPlots !== 1 ? 's' : ''} complete
        {' · '}
        <b style={{ color: '#1a1a2e' }}>₹{Math.round(group.totalBillable).toLocaleString('en-IN')}</b>
      </span>
      <button
        onClick={() => {
          const jobPayments  = groupJob?.payment_history ?? [];
          const jobTotalPaid = groupJob?.summary?.total_paid ?? 0;
          const alreadyBilledAmount = Object.values(billSentMap).reduce(
            (sum: number, log: any) => sum + (Number(log.total_billed) || 0), 0
          );
          const creditAvailable = Math.max(0, jobTotalPaid - alreadyBilledAmount);
          setBillModal({
            farmer:      selectedFarmer,
            jobs:        [groupJob],
            group,
            allPayments: jobPayments,
            // totalPaid:   creditAvailable,
            totalPaid: 0,
          });
        }}
        style={{ padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer', background: balanceDue > 0.01 ? '#1a1a2e' : '#27ae60', color: '#fff' }}
      >
        ✉️ Generate Bill
      </button>
    </>
  );
})() : group.donePlots > 0 ? (
                          <>
                            <span style={{ padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: 700, background: '#fef3e2', color: '#d68910' }}>
                              ◷ In Progress
                            </span>
                            <span style={{ fontSize: 12, color: '#8892a4', flex: 1 }}>
  {group.donePlots}/{group.totalPlots} plots done
  {' · '}
  {group.totalPlots - group.donePlots} remaining:
  {' '}
  <b style={{ color: '#1a1a2e' }}>
    {group.plots.filter(p => !p.isDone).map(p => p.plotName || p.plotCode).join(', ')}
  </b>
  {' · '}
  {group.totalConfirmed > 0 && (
    <>
      <b style={{ color: '#1a1a2e' }}>₹{Math.round(group.totalConfirmed).toLocaleString('en-IN')}</b>
      <span> confirmed</span>
      {' + '}
    </>
  )}
  <b style={{ color: '#d68910' }}>₹{Math.round(group.totalEstimate).toLocaleString('en-IN')}</b>
  <span style={{ color: '#d68910' }}> est.</span>
</span>
                            <button disabled style={{ padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 600, border: 'none', cursor: 'not-allowed', background: '#eef0f4', color: '#aaa' }}>
                              Generate Bill
                            </button>
                          </>
                        ) : (
                          <>
                            <span style={{ padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: 700, background: '#f5f6f8', color: '#999' }}>
                              ⏳ Not Started
                            </span>
                            <span style={{ fontSize: 12, color: '#8892a4', flex: 1 }}>
                              No plots started. Estimated bill:
                              {' '}
                              <b style={{ color: '#1a1a2e' }}>₹{Math.round(group.totalBillable).toLocaleString('en-IN')}</b>
                            </span>
                            <button disabled style={{ padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 600, border: 'none', cursor: 'not-allowed', background: '#eef0f4', color: '#aaa' }}>
                              Generate Bill
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* ── Payment summary section ── */}
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: '#8892a4', marginBottom: 12, marginTop: 8 }}>
                  Payment Summary
                </div>

                <div style={{ background: '#fff', borderRadius: 14, padding: '20px 22px', marginBottom: 16, border: '1px solid #eef0f4' }}>
                  <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                    💰 {selectedFarmer.farmer_name} — All Activities
                  </div>

                  {/* 4-metric grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
                    {[
                        { label: 'Total Job Value', val: `₹${Math.round(jobs.reduce((s,j)=>s+(j.total_job_amount??0),0)).toLocaleString('en-IN')}`, borderColor: '#bdc3c7', bg: '#f8f9fb', color: '#1a1a2e' },
                      { label: 'Total Billed',   val: totalBilled > 0 ? `₹${Math.round(totalBilled).toLocaleString('en-IN')}` : '—', borderColor: '#3498db', bg: '#fff', color: '#3498db' },
                      { label: 'Total Collected', val: `₹${Math.round(totalPaid).toLocaleString('en-IN')}`,    borderColor: '#27ae60', bg: '#fff', color: '#27ae60' },
                      {
                        label: 'Balance Due',
                        val: balanceDue > 0.01 ? `₹${Math.round(balanceDue).toLocaleString('en-IN')}` : '✓ Clear',
                        borderColor: balanceDue > 0.01 ? '#e74c3c' : '#27ae60',
                        bg: balanceDue > 0.01 ? '#fff' : '#e8f8f0',
                        color: balanceDue > 0.01 ? '#e74c3c' : '#27ae60',
                      },
                    ].map((m, i) => (
                      <div key={i} style={{ padding: '12px 14px', borderRadius: 10, borderLeft: `4px solid ${m.borderColor}`, background: m.bg }}>
                        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.6px', color: '#8892a4', marginBottom: 4 }}>{m.label}</div>
                        <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: '-.5px', color: m.color }}>{m.val}</div>
                      </div>
                    ))}
                  </div>

                  {/* Payment history */}
                  {allPayments.length > 0 && (
                    <div style={{ borderTop: '1px solid #eef0f4', paddingTop: 14 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.8px', color: '#8892a4', marginBottom: 10 }}>
                        Payment History
                      </div>
                      {allPayments.map((p, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', padding: '8px 0', borderBottom: i < allPayments.length - 1 ? '1px solid #f8f9fb' : 'none', gap: 12 }}>
                          <div style={{ width: 28, height: 28, borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, flexShrink: 0, background: p.type === 'advance' ? '#fef3e2' : '#e8f8f0', color: p.type === 'advance' ? '#d68910' : '#1e8449' }}>
                            {p.mode === 'UPI' ? '💳' : p.type === 'advance' ? '📧' : p.mode === 'CHEQUE' ? '📋' : '💵'}
                          </div>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 13, fontWeight: 600 }}>
                              {p.type === 'advance' ? 'Advance Payment' : p.mode === 'UPI' ? 'UPI Payment' : p.mode === 'CHEQUE' ? 'Cheque' : p.mode}
                            </div>
                            <div style={{ fontSize: 11, color: '#8892a4' }}>
                              {p.date}{p.notes ? ` · ${p.notes}` : ''}
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 14, fontWeight: 700, color: '#27ae60' }}>
                              +₹{Number(p.amount).toLocaleString('en-IN')}
                            </span>
                            {p.proof_url && (
                              <a href={p.proof_url} target="_blank" rel="noreferrer"
                                style={{ fontSize: 11, color: '#3b82f6', border: '1px solid #bfdbfe', borderRadius: 4, padding: '1px 6px', background: '#eff6ff', textDecoration: 'none' }}>
                                📎 View
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {allPayments.length === 0 && (
                    <div style={{ borderTop: '1px solid #eef0f4', paddingTop: 14, fontSize: 13, color: '#9ca3af', fontStyle: 'italic' }}>
                      No payments recorded yet
                    </div>
                  )}
                </div>
              </div>
            </>
          );
        })()}
      </div>

      {/* Bill modal */}
      {billModal && (
        <ActivityBillModal
          farmer={billModal.farmer} jobs={billModal.jobs} group={billModal.group}
          allPayments={billModal.allPayments} totalPaid={billModal.totalPaid}
          onClose={() => setBillModal(null)}
          onSent={() => { setBillModal(null); fetchData(); }}
        />
      )}

{viewBillModal && (
  <ViewBillModal
    group={viewBillModal.group}
    log={viewBillModal.log}
    onClose={() => setViewBillModal(null)}
    onResend={() => {
      setViewBillModal(null);
      const billSentMap = viewBillModal.jobs[0]?.bill_sent_map ?? {};
      const alreadyBilledAmount = Object.values(billSentMap).reduce(
        (sum: number, log: any) => sum + (Number(log.total_billed) || 0),
        0
      );
      const creditAvailable = Math.max(0, viewBillModal.totalPaid - alreadyBilledAmount);
      setBillModal({
        farmer:      viewBillModal.farmer,
        jobs:        viewBillModal.jobs,
        group:       viewBillModal.group,
        allPayments: viewBillModal.allPayments,
        totalPaid:   creditAvailable,
      });
    }}
  />
)}
    </div>
  );
}