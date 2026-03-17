import { useState, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';

export default function MukkadamPayout() {
  const [data, setData]               = useState<any>(null);
  const [loading, setLoading]         = useState(true);
  const [expanded, setExpanded]       = useState<number | null>(null);
  const [activeTab, setActiveTab]     = useState<Record<number, string>>({});
  const [showAddEntry, setShowAddEntry] = useState<number | null>(null);
  const [payModal, setPayModal]       = useState<any>(null);
  const [clusterView, setClusterView] = useState<number | null>(null);
  const [clusterData, setClusterData] = useState<any>(null);
  const [clusterLoading, setClusterLoading] = useState(false);
  const [focusMukkadamId, setFocusMukkadamId] = useState<number | null>(null);

  const getTab = (id: number) => activeTab[id] || 'timeline';
  const setTab = (id: number, t: string) => setActiveTab(p => ({ ...p, [id]: t }));

  const fmt  = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`;
  const fmtK = (n: number) => n >= 100000 ? `₹${(n/100000).toFixed(1)}L` : n >= 1000 ? `₹${(n/1000).toFixed(1)}k` : `₹${n}`;

  // ── fetch overview ────────────────────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    fetch(`${API_BASE_URL}/api/mukkadam-payment-overview/`, {
      headers: { Authorization: `Token ${token}` },
    })
      .then(r => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // ── fetch cluster detail when drilling in ─────────────────────────────────
  useEffect(() => {
    if (!clusterView) return;
    setClusterLoading(true);
    setClusterData(null);
    const token = localStorage.getItem('auth_token');
    fetch(`${API_BASE_URL}/api/cluster/${clusterView}/payment-dashboard/`, {
      headers: { Authorization: `Token ${token}` },
    })
      .then(r => r.json())
      .then(d => {
        setClusterData(d);
        if (focusMukkadamId) {
          setExpanded(focusMukkadamId);
          setTab(focusMukkadamId, 'timeline');
          setTimeout(() => {
            document.getElementById(`mc-${focusMukkadamId}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }, 120);
        }
      })
      .catch(console.error)
      .finally(() => setClusterLoading(false));
  }, [clusterView]);

  // ── helpers ───────────────────────────────────────────────────────────────

  const Chip = ({ status }: { status: string }) => {
    const cfg: Record<string, any> = {
      paid:                 { bg: '#f0fdf4', color: '#16a34a', border: '#bbf7d0', label: '✓ Paid'    },
      due:                  { bg: '#fefce8', color: '#ca8a04', border: '#fde68a', label: '⏳ Due'     },
      pending_verification: { bg: '#fff7ed', color: '#ea580c', border: '#fed7aa', label: '⏳ Pending' },
      na:                   { bg: '#f5f5f4', color: '#a3a398', border: '#e8e5de', label: 'N/A'       },
    };
    const s = cfg[status] ?? cfg.na;
    return <span style={{ display: 'inline-flex', padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>{s.label}</span>;
  };

  const ModeBadge = ({ type }: { type: string }) => {
    const cfg: Record<string, any> = {
      permanent: { bg: '#f0fdf4', color: '#16a34a', border: '#bbf7d0', label: '📋 Settlement Schedule' },
      updown:    { bg: '#fff7ed', color: '#ea580c', border: '#fed7aa', label: '🔄 Up-Down' },
      mixed:     { bg: '#f5f3ff', color: '#7c3aed', border: '#ddd6fe', label: '📋 Settlement Schedule (Mixed)' },
    };
    const s = cfg[type] ?? { bg: '#f5f4ef', color: '#a3a398', border: '#e8e5de', label: type };
    return <span style={{ padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 700, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>{s.label}</span>;
  };

  const VerifiedByTag = ({ name }: { name: string | null }) => name ? (
    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#f0fdf4', color: '#16a34a', fontWeight: 600, border: '1px solid #bbf7d0' }}>✓ {name}</span>
  ) : (
    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#fff7ed', color: '#ea580c', fontWeight: 600, border: '1px solid #fed7aa' }}>⏳ Awaiting admin</span>
  );

  const Bar = ({ pct }: { pct: number }) => {
    const color = pct > 60 ? '#16a34a' : pct > 25 ? '#ea580c' : '#dc2626';
    return (
      <div style={{ background: '#f0ede7', borderRadius: 4, height: 4, width: '100%', overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', borderRadius: 4, background: color, transition: 'width 0.4s' }} />
      </div>
    );
  };

  // ── loading ───────────────────────────────────────────────────────────────
  if (loading || !data) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '64px 0' }}>
      <RefreshCw size={28} style={{ color: '#7c3aed', animation: 'spin 1s linear infinite' }} />
    </div>
  );

  const pipe     = data.pipeline ?? {};
  const clBill   = data.cluster_billing ?? [];
  const weekDue  = data.weekly_due_list ?? [];
  const settPend = data.settlement_list ?? [];
  const vQueue   = data.verification_queue ?? [];
  const recent   = data.recent_payments ?? [];

  // ══════════════════════════════════════════════════════════════════════════
  // CLUSTER DRILL-IN VIEW
  // ══════════════════════════════════════════════════════════════════════════
  if (clusterView) {
    const clusterName = clBill.find((c: any) => c.cluster_id === clusterView)?.cluster_name ?? 'Cluster';

    return (
      <div style={{ height: 'calc(100vh - 200px)', overflow: 'hidden', margin: '-20px -24px' }}>
        {/* Back bar */}
        <div style={{ padding: '12px 24px', background: '#fff', borderBottom: '1px solid #e8e5de', display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={() => { setClusterView(null); setFocusMukkadamId(null); setExpanded(null); }}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 8, border: '1px solid #e8e5de', background: '#fff', fontSize: 12, fontWeight: 600, color: '#6b6b63', cursor: 'pointer', fontFamily: 'inherit' }}>
            ← Back to Overview
          </button>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a' }}>{clusterName} — Mukkadams</span>
        </div>

        <div style={{ height: 'calc(100% - 49px)', overflow: 'auto', padding: '20px 24px' }}>
          {clusterLoading || !clusterData ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#a3a398', fontSize: 13 }}>Loading mukkadam data...</div>
          ) : (
            (clusterData.mukkadams ?? []).map((m: any) => {
              const isExp       = expanded === m.mukkadam_id;
              const currentTab  = getTab(m.mukkadam_id);
              const isUpdown    = m.mukkadam_type === 'updown';
              const isPermanent = m.mukkadam_type === 'permanent';

              const txns: any[]    = m.transaction_history ?? [];
              const advancePaid    = Math.abs(txns.filter((t: any) => t.type === 'advance').reduce((s: number, t: any) => s + t.amount, 0));
              const weeklyPaid     = m.total_weekly_paid ?? 0;
              const settlePaid     = (m.settlements ?? []).filter((s: any) => s.status === 'paid').reduce((sum: number, s: any) => sum + s.net_payable, 0);
              const structuredPaid = advancePaid + weeklyPaid + settlePaid + (m.transport_price ?? 0);
              const miscCosts      = (m.settlements ?? []).flatMap((s: any) => s.misc_costs ?? []);
              const adhocTot       = miscCosts.reduce((sum: number, c: any) => sum + c.amount, 0);
              const totalOut       = structuredPaid + adhocTot;
              const settlesPending = (m.settlements ?? []).filter((s: any) => s.status === 'calculated' && s.net_payable > 0);
              const missedCount    = m.missed_weekly_dates?.length ?? 0;
              const hasAction      = settlesPending.length > 0 || missedCount > 0;
              const allAllocs: any[] = (m.settlements ?? []).flatMap((s: any) => s.activities ?? []);
              const totalAcres     = allAllocs.reduce((sum: number, a: any) => sum + (a.allocated_area || 0), 0);
              const completedAcres = allAllocs.filter((a: any) => a.work_status === 'completed').reduce((sum: number, a: any) => sum + (a.allocated_area || 0), 0);
              const acrePct        = totalAcres > 0 ? (completedAcres / totalAcres) * 100 : 0;
              const initials       = m.mukkadam_name.split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase();
              const paidCount      = txns.filter((t: any) => t.amount !== 0).length;

              return (
                <div key={m.mukkadam_id} id={`mc-${m.mukkadam_id}`} style={{ background: '#fff', borderRadius: 12, border: `1px solid ${hasAction ? '#fed7aa' : '#e8e5de'}`, marginBottom: 10, overflow: 'hidden' }}>

                  {/* ── CARD HEADER ── */}
                  <div
                    onClick={() => setExpanded(isExp ? null : m.mukkadam_id)}
                    style={{ padding: '12px 16px', cursor: 'pointer', display: 'grid', gridTemplateColumns: '2.5fr 120px 90px 90px 90px 90px 30px', alignItems: 'center', gap: 8 }}
                    onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = '#fafaf8'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 38, height: 38, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, background: isUpdown ? '#fff7ed' : '#f0fdf4', border: `2px solid ${isUpdown ? '#fed7aa' : '#bbf7d0'}`, color: isUpdown ? '#ea580c' : '#16a34a' }}>
                        {initials}
                      </div>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 14, fontWeight: 700 }}>{m.mukkadam_name}</span>
                          <ModeBadge type={m.mukkadam_type} />
                          {settlesPending.length > 0 && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: '#fff7ed', color: '#ea580c', fontWeight: 700 }}>⏳ Verify</span>}
                          {miscCosts.length > 0 && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: '#f5f3ff', color: '#7c3aed', fontWeight: 700 }}>📝 {miscCosts.length}</span>}
                          <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: '#eff6ff', color: '#2563eb', fontWeight: 700, border: '1px solid #bfdbfe' }}>📒 {paidCount} payments</span>
                        </div>
                        <div style={{ fontSize: 11, color: '#a3a398', marginTop: 1 }}>
                          {m.crew_size} crew · {isUpdown ? 'Up-Down' : 'Permanent'}
                          {missedCount > 0 && <span style={{ color: '#dc2626', fontWeight: 600 }}> · ⚠️ {missedCount} missed weekly</span>}
                        </div>
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: 10, color: '#a3a398', marginBottom: 3 }}>Work</div>
                      <Bar pct={acrePct} />
                      <div style={{ fontSize: 10, color: '#6b6b63', marginTop: 2 }}>{completedAcres.toFixed(1)}/{totalAcres.toFixed(1)} ac</div>
                    </div>
                    <div style={{ textAlign: 'right' }}><div style={{ fontSize: 10, color: '#a3a398' }}>Scheduled</div><div style={{ fontSize: 14, fontWeight: 700, color: '#16a34a' }}>{fmtK(structuredPaid)}</div></div>
                    <div style={{ textAlign: 'right' }}><div style={{ fontSize: 10, color: '#a3a398' }}>Daily</div><div style={{ fontSize: 14, fontWeight: 700, color: '#a3a398' }}>—</div></div>
                    <div style={{ textAlign: 'right' }}><div style={{ fontSize: 10, color: '#a3a398' }}>Ad-hoc</div><div style={{ fontSize: 14, fontWeight: 700, color: adhocTot > 0 ? '#7c3aed' : '#a3a398' }}>{adhocTot > 0 ? fmtK(adhocTot) : '—'}</div></div>
                    <div style={{ textAlign: 'right' }}><div style={{ fontSize: 10, color: '#a3a398' }}>Total Out</div><div style={{ fontSize: 14, fontWeight: 800 }}>{fmtK(totalOut)}</div></div>
                    <div style={{ textAlign: 'center', color: '#a3a398', fontSize: 13 }}>{isExp ? '▲' : '▼'}</div>
                  </div>

                  {/* ── EXPANDED ── */}
                  {isExp && (
                    <div style={{ borderTop: '1px solid #f0ede7' }}>
                      <div style={{ padding: '8px 16px', background: '#fafaf8', borderBottom: '1px solid #f0ede7', fontSize: 12, color: '#6b6b63', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <ModeBadge type={m.mukkadam_type} />
                        <span>{isPermanent ? 'Settlement schedule throughout.' : 'Up-Down — transport costs apply per allocation.'}</span>
                      </div>

                      {/* Tabs */}
                      <div style={{ display: 'flex', borderBottom: '1px solid #e8e5de' }}>
                        {[
                          { key: 'timeline', label: '📋 Payments' },
                          { key: 'adhoc',    label: `📝 Manual Entries (${miscCosts.length})` },
                          { key: 'recon',    label: '🔍 Reconciliation' },
                        ].map(t => (
                          <button key={t.key} onClick={() => setTab(m.mukkadam_id, t.key)} style={{ padding: '10px 16px', border: 'none', cursor: 'pointer', background: 'transparent', fontSize: 12, fontWeight: 600, fontFamily: 'inherit', color: currentTab === t.key ? '#2563eb' : '#a3a398', borderBottom: currentTab === t.key ? '2px solid #2563eb' : '2px solid transparent' }}>
                            {t.label}
                          </button>
                        ))}
                      </div>

                      {/* ── TAB: PAYMENTS ── */}
                      {currentTab === 'timeline' && (
                        <div style={{ padding: '14px 16px' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                            {/* LEFT */}
                            <div>
                              <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', marginBottom: 8 }}>One-Time Payments</div>
                              <div style={{ background: '#fafaf8', borderRadius: 10, border: '1px solid #f0ede7', overflow: 'hidden' }}>
                                {m.advance_amount > 0 && (
                                  <div style={{ padding: '10px 12px', borderBottom: '1px solid #f0ede7' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                      <div><div style={{ fontSize: 13, fontWeight: 600 }}>Advance Payment</div><div style={{ marginTop: 3 }}><VerifiedByTag name="Paid" /></div></div>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(m.advance_amount)}</span><Chip status="paid" /></div>
                                    </div>
                                  </div>
                                )}
                                {isUpdown && m.transport_price > 0 && (
                                  <div style={{ padding: '10px 12px', borderBottom: '1px solid #f0ede7' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                      <div style={{ fontSize: 13, fontWeight: 600 }}>🚛 Transport (Up-Down)</div>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(m.transport_price)}</span><Chip status="paid" /></div>
                                    </div>
                                  </div>
                                )}
                              </div>

                              {(m.settlements ?? []).length > 0 && (
                                <div style={{ marginTop: 14 }}>
                                  <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', marginBottom: 8 }}>Acre Settlements</div>
                                  {(m.settlements ?? []).map((s: any, si: number) => {
                                    const sc: Record<string, any> = { paid: { bg: '#f0fdf4', border: '#bbf7d0' }, calculated: { bg: '#fff7ed', border: '#fed7aa' }, pending: { bg: '#fefce8', border: '#fde68a' }, no_payment_needed: { bg: '#f0fdf4', border: '#bbf7d0' } };
                                    const c = sc[s.status] ?? sc.pending;
                                    return (
                                      <div key={si} style={{ background: c.bg, borderRadius: 10, padding: 14, border: `1px solid ${c.border}`, marginBottom: 8, fontSize: 12 }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}><div style={{ fontWeight: 700, fontSize: 13 }}>{s.farmer_name}</div><Chip status={s.status} /></div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>Gross</span><span style={{ fontWeight: 600 }}>{fmt(s.gross_amount)}</span></div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>10% Holdback</span><span style={{ color: '#dc2626' }}>−{fmt(s.deposit_held)}</span></div>
                                        {isUpdown && s.transport_deducted > 0 && <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>🚛 Transport added</span><span style={{ color: '#ea580c' }}>+{fmt(s.transport_deducted)}</span></div>}
                                        {s.advance_deducted > 0 && <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>Advance adjusted</span><span style={{ color: '#dc2626' }}>−{fmt(s.advance_deducted)}</span></div>}
                                        {s.weekly_payments_deducted > 0 && <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>Weekly deducted</span><span style={{ color: '#dc2626' }}>−{fmt(s.weekly_payments_deducted)}</span></div>}
                                        {s.deposit_carried_forward > 0 && <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}><span style={{ color: '#6b6b63' }}>Deposit released</span><span style={{ color: '#16a34a' }}>+{fmt(s.deposit_carried_forward)}</span></div>}
                                        <div style={{ borderTop: `1px solid ${c.border}`, paddingTop: 6, marginTop: 4, display: 'flex', justifyContent: 'space-between' }}><span style={{ fontWeight: 700 }}>Net Payable</span><span style={{ fontWeight: 800, fontSize: 16, color: '#ea580c' }}>{fmt(s.net_payable)}</span></div>
                                        {s.status === 'calculated' && s.net_payable > 0 && (
                                          <button style={{ marginTop: 10, width: '100%', padding: '10px', borderRadius: 10, border: 'none', background: '#16a34a', color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>✓ Verify & Approve — {fmt(s.net_payable)}</button>
                                        )}
                                        {s.status === 'pending' && <div style={{ marginTop: 8, fontSize: 11, color: '#a3a398', textAlign: 'center' }}>Settlement triggers after all activities complete</div>}
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>

                            {/* RIGHT */}
                            <div>
                              <div style={{ fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', marginBottom: 8 }}>Weekly ({m.weekly_payment_day_label ?? 'Saturday'})</div>
                              <div style={{ background: '#fafaf8', borderRadius: 10, border: '1px solid #f0ede7', overflow: 'hidden' }}>
                                {txns.filter((t: any) => t.type === 'weekly').length === 0 && <div style={{ padding: 20, textAlign: 'center', color: '#a3a398', fontSize: 12 }}>No weekly payments yet</div>}
                                {txns.filter((t: any) => t.type === 'weekly').map((w: any, j: number) => (
                                  <div key={j} style={{ padding: '10px 12px', borderBottom: '1px solid #f0ede7' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                      <div><div style={{ fontSize: 13, fontWeight: 600 }}>Weekly — {w.date?.slice(5).replace('-', ' ')}</div>{w.notes && <div style={{ fontSize: 10, color: '#a3a398', marginTop: 2 }}>{w.notes}</div>}</div>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(Math.abs(w.amount))}</span><Chip status="paid" /></div>
                                    </div>
                                  </div>
                                ))}
                                {(m.missed_weekly_dates ?? []).map((d: string, j: number) => (
                                  <div key={`miss-${j}`} style={{ padding: '10px 12px', borderBottom: '1px solid #f0ede7', background: '#fefce8' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                      <div><div style={{ fontSize: 13, fontWeight: 600 }}>Weekly — {d.slice(5).replace('-', ' ')}</div><div style={{ fontSize: 10, color: '#dc2626', marginTop: 2 }}>⚠️ Missed</div></div>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(m.weekly_payment_amount ?? 0)}</span>
                                        <Chip status="due" />
                                        <button onClick={e => { e.stopPropagation(); setPayModal({ mukkadam: m, assignmentId: m.assignment_id, defaultDate: d }); }} style={{ padding: '6px 16px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>💰 Pay</button>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                                {!m.already_paid_today && (m.missed_weekly_dates ?? []).length === 0 && (
                                  <div style={{ padding: '10px 12px', background: '#fefce8', borderTop: txns.filter((t: any) => t.type === 'weekly').length > 0 ? '1px solid #f0ede7' : 'none' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                      <div><div style={{ fontSize: 13, fontWeight: 600 }}>Next Weekly Payment</div><div style={{ fontSize: 10, color: '#a3a398' }}>{m.weekly_payment_day_label ?? 'Saturday'}</div></div>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <span style={{ fontSize: 14, fontWeight: 700 }}>{fmt(m.weekly_payment_amount ?? 0)}</span>
                                        <Chip status="due" />
                                        <button onClick={e => { e.stopPropagation(); setPayModal({ mukkadam: m, assignmentId: m.assignment_id }); }} style={{ padding: '6px 16px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>💰 Pay</button>
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
                              <div style={{ marginTop: 4, padding: '6px 12px', fontSize: 11, color: '#0d9488', background: '#f0fdfa', borderRadius: 6, border: '1px solid #99f6e4' }}>
                                ℹ️ Weekly payments don't need admin verification — direct pay.
                              </div>
                              <div style={{ marginTop: 14, background: '#f5f3ff', borderRadius: 10, padding: 14, border: '1px solid #ddd6fe' }}>
                                <div style={{ fontSize: 11, fontWeight: 700, color: '#7c3aed', marginBottom: 8 }}>💰 Payment Summary</div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '4px 12px', fontSize: 12 }}>
                                  <span style={{ color: '#6b6b63' }}>Advance</span><span style={{ fontWeight: 700, color: '#16a34a', textAlign: 'right' }}>{fmt(m.advance_amount ?? 0)}</span>
                                  {(m.transport_price ?? 0) > 0 && <><span style={{ color: '#6b6b63' }}>Transport</span><span style={{ fontWeight: 700, color: '#ea580c', textAlign: 'right' }}>{fmt(m.transport_price)}</span></>}
                                  <span style={{ color: '#6b6b63' }}>Weekly Paid</span><span style={{ fontWeight: 700, color: '#16a34a', textAlign: 'right' }}>{fmt(weeklyPaid)}</span>
                                  <span style={{ color: '#6b6b63' }}>Settlements Paid</span><span style={{ fontWeight: 700, color: '#2563eb', textAlign: 'right' }}>{fmt(settlePaid)}</span>
                                  {adhocTot > 0 && <><span style={{ color: '#6b6b63' }}>Ad-hoc / Manual</span><span style={{ fontWeight: 700, color: '#7c3aed', textAlign: 'right' }}>{fmt(adhocTot)}</span></>}
                                  <span style={{ color: '#6b6b63', fontWeight: 700, borderTop: '1px solid #ddd6fe', paddingTop: 4 }}>Total Outflows</span>
                                  <span style={{ fontWeight: 800, textAlign: 'right', borderTop: '1px solid #ddd6fe', paddingTop: 4 }}>{fmt(totalOut)}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* ── TAB: MANUAL ENTRIES ── */}
                      {currentTab === 'adhoc' && (
                        <div style={{ padding: '14px 16px' }}>
                          <div onClick={() => setShowAddEntry(showAddEntry === m.mukkadam_id ? null : m.mukkadam_id)} style={{ padding: '16px 20px', borderRadius: 12, cursor: 'pointer', border: '2px dashed #ddd6fe', background: showAddEntry === m.mukkadam_id ? '#f5f3ff' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 14 }}
                            onMouseEnter={e => { if (showAddEntry !== m.mukkadam_id) (e.currentTarget as HTMLDivElement).style.background = '#f5f3ff'; }}
                            onMouseLeave={e => { if (showAddEntry !== m.mukkadam_id) (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                          >
                            <span style={{ fontSize: 24, color: '#7c3aed' }}>+</span>
                            <div><div style={{ fontSize: 14, fontWeight: 700, color: '#7c3aed' }}>Add Manual Entry</div><div style={{ fontSize: 11, color: '#6b6b63' }}>Wedding advance, bonus, adjustment, deduction, or any off-schedule payment</div></div>
                          </div>
                          {showAddEntry === m.mukkadam_id && (
                            <div style={{ background: '#f5f3ff', borderRadius: 12, padding: 18, border: '1px solid #ddd6fe', marginBottom: 14 }}>
                              <div style={{ fontSize: 13, fontWeight: 700, color: '#7c3aed', marginBottom: 12 }}>New Manual Entry</div>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                <div><div style={{ fontSize: 11, color: '#6b6b63', marginBottom: 4, fontWeight: 600 }}>Type</div><select style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, background: '#fff', fontFamily: 'inherit' }}><option>💒 Wedding Advance</option><option>➕ Extra Payment</option><option>🎉 Festival Bonus</option><option>➖ Deduction</option><option>🔄 Adjustment</option><option>📝 Other</option></select></div>
                                <div><div style={{ fontSize: 11, color: '#6b6b63', marginBottom: 4, fontWeight: 600 }}>Amount (₹)</div><input placeholder="Enter amount" style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, boxSizing: 'border-box' as const, fontFamily: 'inherit' }} /></div>
                                <div><div style={{ fontSize: 11, color: '#6b6b63', marginBottom: 4, fontWeight: 600 }}>Date</div><input type="date" style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, boxSizing: 'border-box' as const, fontFamily: 'inherit' }} /></div>
                                <div><div style={{ fontSize: 11, color: '#6b6b63', marginBottom: 4, fontWeight: 600 }}>Adjust in Settlement?</div><select style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, background: '#fff', fontFamily: 'inherit' }}><option>Yes — deduct from acre/final settlement</option><option>No — separate payment, don't deduct</option></select></div>
                              </div>
                              <div style={{ marginTop: 12 }}><div style={{ fontSize: 11, color: '#6b6b63', marginBottom: 4, fontWeight: 600 }}>Note / Reason</div><input placeholder="Why is this payment being made..." style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, boxSizing: 'border-box' as const, fontFamily: 'inherit' }} /></div>
                              <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 8, background: '#fff7ed', border: '1px solid #fed7aa', fontSize: 11, color: '#ea580c' }}>🔐 This entry will be submitted for <strong>Payment Admin verification</strong> before payment is released.</div>
                              <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
                                <button onClick={() => setShowAddEntry(null)} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e8e5de', background: '#fff', color: '#6b6b63', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>Cancel</button>
                                <button style={{ padding: '8px 24px', borderRadius: 8, border: 'none', background: '#7c3aed', color: '#fff', fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>Submit for Verification</button>
                              </div>
                            </div>
                          )}
                          {miscCosts.length === 0 && showAddEntry !== m.mukkadam_id ? (
                            <div style={{ padding: 32, textAlign: 'center', color: '#a3a398' }}>No manual entries yet.</div>
                          ) : miscCosts.length > 0 && (
                            <div style={{ background: '#fafaf8', borderRadius: 10, border: '1px solid #f0ede7', overflow: 'hidden' }}>
                              {miscCosts.map((e: any, j: number) => (
                                <div key={j} style={{ padding: '12px 14px', borderBottom: j < miscCosts.length - 1 ? '1px solid #f0ede7' : 'none' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div><div style={{ fontSize: 13, fontWeight: 600 }}>{e.reason}</div><div style={{ fontSize: 10, color: '#a3a398', marginTop: 4 }}>{e.created_at}</div></div>
                                    <span style={{ fontSize: 15, fontWeight: 700 }}>{fmt(e.amount)}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* ── TAB: RECONCILIATION ── */}
                      {currentTab === 'recon' && (
                        <div style={{ padding: '14px 16px' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                            <div style={{ background: '#f0fdf4', borderRadius: 10, padding: 14, border: '1px solid #bbf7d0' }}>
                              <div style={{ fontSize: 11, fontWeight: 700, color: '#16a34a', marginBottom: 10 }}>📊 SYSTEM-CALCULATED (Earned)</div>
                              <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                                {(m.settlements ?? []).map((s: any, i: number) => (
                                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between' }}><span>{s.farmer_name} ({s.job_id})</span><span style={{ fontWeight: 700 }}>{fmt(s.gross_amount)}</span></div>
                                ))}
                                <div style={{ borderTop: '1px solid #bbf7d0', paddingTop: 4, marginTop: 2, display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
                                  <span>Total Earned</span><span style={{ fontSize: 16, color: '#16a34a' }}>{fmt((m.settlements ?? []).reduce((s: number, x: any) => s + x.gross_amount, 0))}</span>
                                </div>
                              </div>
                            </div>
                            <div style={{ background: '#fff7ed', borderRadius: 10, padding: 14, border: '1px solid #fed7aa' }}>
                              <div style={{ fontSize: 11, fontWeight: 700, color: '#ea580c', marginBottom: 10 }}>💸 ACTUAL OUTFLOWS</div>
                              <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Structured payments</span><span style={{ fontWeight: 600 }}>{fmt(structuredPaid)}</span></div>
                                {adhocTot > 0 && <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Ad-hoc / Manual</span><span style={{ fontWeight: 600, color: '#7c3aed' }}>{fmt(adhocTot)}</span></div>}
                                <div style={{ borderTop: '1px solid #fed7aa', paddingTop: 4, marginTop: 2, display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
                                  <span>Total Outflows</span><span style={{ fontSize: 16, color: '#ea580c' }}>{fmt(totalOut)}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                          {(() => {
                            const earned  = (m.settlements ?? []).reduce((s: number, x: any) => s + x.gross_amount, 0);
                            const diff    = totalOut - earned;
                            const isOver  = diff > 5000;
                            const isUnder = diff < -5000;
                            return (
                              <div style={{ marginTop: 14, padding: 14, borderRadius: 10, background: isOver ? '#fef2f2' : isUnder ? '#fefce8' : '#f0fdf4', border: `1.5px solid ${isOver ? '#fecaca' : isUnder ? '#fde68a' : '#bbf7d0'}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                  <div style={{ fontSize: 13, fontWeight: 700, color: isOver ? '#dc2626' : isUnder ? '#ca8a04' : '#16a34a' }}>{isOver ? '⚠️ OVERPAID' : isUnder ? '📉 UNDERPAID' : '✅ WITHIN RANGE'}</div>
                                  <div style={{ fontSize: 11, color: '#6b6b63', marginTop: 2 }}>{!isOver && !isUnder ? 'Difference within expected range.' : isOver ? 'More paid than earned.' : 'Significant earnings gap — settlements pending.'}</div>
                                </div>
                                <div style={{ fontSize: 22, fontWeight: 800, color: isOver ? '#dc2626' : isUnder ? '#ca8a04' : '#16a34a' }}>{diff > 0 ? '+' : ''}{fmt(Math.abs(diff))}</div>
                              </div>
                            );
                          })()}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Weekly Pay Modal */}
        {payModal && (
          <WeeklyPayModal
            mukkadam={payModal.mukkadam}
            assignmentId={payModal.assignmentId}
            defaultDate={payModal.defaultDate}
            onClose={() => setPayModal(null)}
            onSaved={() => {
              setPayModal(null);
              const token = localStorage.getItem('auth_token');
              fetch(`${API_BASE_URL}/api/cluster/${clusterView}/payment-dashboard/`, {
                headers: { Authorization: `Token ${token}` },
              }).then(r => r.json()).then(setClusterData);
            }}
          />
        )}
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // OVERVIEW
  // ══════════════════════════════════════════════════════════════════════════
  return (
    <div>
      {/* ── Pipeline KPI cards ── */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>MUKKADAM PAYOUT PIPELINE</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
          {[
            { icon: '📅', label: 'Weekly Due',        val: pipe.weekly_due?.count ?? 0,            amount: pipe.weekly_due?.amount ?? 0,        color: '#ca8a04', bg: '#fefce8', border: '#fde68a', sub: 'Mukkadams to pay today' },
            { icon: '💰', label: 'Settlement Pending', val: pipe.settlement_pending?.count ?? 0,    amount: pipe.settlement_pending?.amount ?? 0, color: '#dc2626', bg: '#fef2f2', border: '#fecaca', sub: 'Acre settlements due' },
            { icon: '✅', label: 'Total Paid Out',     val: fmtK(pipe.total_paid_out?.amount ?? 0), amount: 0, noCount: true,                     color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', sub: 'All time' },
            { icon: '👷', label: 'Mukkadams Active',  val: pipe.mukkadams_active?.count ?? 0,      amount: 0,                                     color: '#7c3aed', bg: '#f5f3ff', border: '#ddd6fe', sub: 'Across all clusters' },
          ].map((card, i) => (
            <div key={i} style={{ flex: 1, minWidth: 140, background: card.bg, borderRadius: 12, border: `1.5px solid ${card.border}`, padding: '16px 18px', textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: card.color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>{card.icon} {card.label}</div>
              <div style={{ fontSize: 28, fontWeight: 800, color: card.color, lineHeight: 1.1 }}>{card.val}</div>
              {!(card as any).noCount && card.amount > 0 && <div style={{ fontSize: 15, fontWeight: 700, color: card.color, marginTop: 4 }}>{`₹${Math.round(card.amount).toLocaleString('en-IN')}`}</div>}
              <div style={{ fontSize: 11, color: '#a3a398', marginTop: 4 }}>{card.sub}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Verification Queue ── */}
      {vQueue.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{ fontSize: 15 }}>🔐</span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>Payment Admin — Verification Queue</span>
            <span style={{ padding: '2px 10px', borderRadius: 10, fontSize: 12, fontWeight: 700, background: '#fff7ed', color: '#ea580c', border: '1px solid #fed7aa' }}>{vQueue.length} pending</span>
            <span style={{ fontSize: 12, color: '#6b6b63' }}>— Weekly payments don't need verification. All others do.</span>
          </div>
          <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #fed7aa', overflow: 'hidden' }}>
            {vQueue.map((q: any, i: number) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', borderBottom: i < vQueue.length - 1 ? '1px solid #f0ede7' : 'none', background: q.urgency === 'high' ? 'rgba(254,243,199,0.2)' : 'transparent' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: q.urgency === 'high' ? '#dc2626' : q.urgency === 'medium' ? '#ea580c' : '#ca8a04' }} />
                <div style={{ fontWeight: 600, minWidth: 160, fontSize: 13 }}>{q.mukkadam_name}</div>
                <span style={{ padding: '2px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: '#f5f3ff', color: '#7c3aed', border: '1px solid #ddd6fe' }}>{q.reason ?? q.label}</span>
                {q.created_by && <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#eff6ff', color: '#2563eb', fontWeight: 600, border: '1px solid #bfdbfe' }}>✏️ {q.created_by}</span>}
                <div style={{ flex: 1 }} />
                <div style={{ fontSize: 15, fontWeight: 700 }}>{fmt(q.amount)}</div>
                <button onClick={async () => {
                  const token = localStorage.getItem('auth_token');
                  await fetch(`${API_BASE_URL}/api/mukkadam-misc-cost/${q.cost_id}/verify/`, { method: 'POST', headers: { Authorization: `Token ${token}` } });
                  const res = await fetch(`${API_BASE_URL}/api/mukkadam-payment-overview/`, { headers: { Authorization: `Token ${token}` } });
                  setData(await res.json());
                }} style={{ padding: '6px 14px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>✓ Verify & Pay</button>
                <button style={{ padding: '6px 8px', borderRadius: 6, border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' }}>✗</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Weekly Due ── */}
      {weekDue.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>📅 Weekly Payments Due Today</div>
          <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #fde68a', overflow: 'hidden' }}>
            {weekDue.map((w: any, i: number) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderBottom: i < weekDue.length - 1 ? '1px solid #f0ede7' : 'none' }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#fefce8', border: '1.5px solid #fde68a', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#ca8a04', flexShrink: 0 }}>
                  {w.mukkadam_name.split(' ').map((x: string) => x[0]).join('').slice(0, 2).toUpperCase()}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{w.mukkadam_name}</div>
                  <div style={{ fontSize: 11, color: '#a3a398' }}>{w.cluster_name} · {w.mukkadam_type === 'updown' ? 'Up-Down' : 'Permanent'}{w.days_overdue > 0 && <span style={{ color: '#dc2626', fontWeight: 600 }}> · {w.days_overdue}d overdue</span>}</div>
                </div>
                <div style={{ fontWeight: 700, fontSize: 14, color: '#ca8a04' }}>{fmt(w.weekly_amount)}</div>
                <button onClick={() => setClusterView(w.cluster_id)} style={{ padding: '6px 16px', borderRadius: 8, border: '1px solid #fde68a', background: '#fefce8', color: '#ca8a04', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>Pay →</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Settlement Pending ── */}
      {settPend.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>💰 Settlement Pending</div>
          <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #fecaca', overflow: 'hidden' }}>
            {settPend.map((s: any, i: number) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderBottom: i < settPend.length - 1 ? '1px solid #f0ede7' : 'none' }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#fef2f2', border: '1.5px solid #fecaca', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#dc2626', flexShrink: 0 }}>
                  {s.mukkadam_name.split(' ').map((x: string) => x[0]).join('').slice(0, 2).toUpperCase()}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{s.mukkadam_name}</div>
                  <div style={{ fontSize: 11, color: '#a3a398' }}>{s.cluster_name} · Job #{s.job_id}{s.mukkadam_type === 'updown' ? ' · Up-Down' : ' · Permanent'}{s.calculated_at && ` · Calculated ${s.calculated_at}`}</div>
                </div>
                <div><div style={{ fontWeight: 700, fontSize: 14, color: '#dc2626' }}>{fmt(s.net_payable)}</div><div style={{ fontSize: 10, color: '#a3a398', textAlign: 'right' }}>Net payable</div></div>
                <button onClick={() => { setFocusMukkadamId(s.mukkadam_id); setClusterView(s.cluster_id); }} style={{ padding: '6px 16px', borderRadius: 8, border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>Settle →</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Cluster Billing Summary ── */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>📊 Cluster-wise Mukkadam Outflows</div>
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(160px,2fr) 70px 100px 100px 100px 100px', padding: '10px 16px', fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.05em', background: '#fafaf8', borderBottom: '1px solid #e8e5de' }}>
            <div>Cluster</div><div style={{ textAlign: 'right' }}>Teams</div><div style={{ textAlign: 'right' }}>Weekly Paid</div><div style={{ textAlign: 'right' }}>Settled</div><div style={{ textAlign: 'right' }}>Pending</div><div style={{ textAlign: 'right' }}>Weekly Due</div>
          </div>
          {clBill.map((c: any, i: number) => (
            <div key={c.cluster_id} onClick={() => setClusterView(c.cluster_id)}
              style={{ display: 'grid', gridTemplateColumns: 'minmax(160px,2fr) 70px 100px 100px 100px 100px', padding: '10px 16px', fontSize: 13, alignItems: 'center', borderBottom: i < clBill.length - 1 ? '1px solid #f0ede7' : 'none', cursor: 'pointer', transition: 'background 0.1s' }}
              onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = '#fafaf8'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
            >
              <div style={{ fontWeight: 600 }}>{c.cluster_name}</div>
              <div style={{ textAlign: 'right', color: '#6b6b63' }}>{c.mukkadams}</div>
              <div style={{ textAlign: 'right', color: '#16a34a', fontWeight: 600 }}>{fmtK(c.weekly_paid)}</div>
              <div style={{ textAlign: 'right', color: '#2563eb', fontWeight: 600 }}>{fmtK(c.settlement_paid)}</div>
              <div style={{ textAlign: 'right', fontWeight: 700, color: c.settlement_pending > 0 ? '#dc2626' : '#16a34a' }}>{c.settlement_pending > 0 ? fmtK(c.settlement_pending) : '✓'}</div>
              <div style={{ textAlign: 'right', fontWeight: 700, color: c.weekly_due > 0 ? '#ca8a04' : '#16a34a' }}>{c.weekly_due > 0 ? fmtK(c.weekly_due) : '✓'}</div>
            </div>
          ))}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(160px,2fr) 70px 100px 100px 100px 100px', padding: '10px 16px', fontSize: 13, fontWeight: 700, background: '#f5f4ef', borderTop: '2px solid #e8e5de' }}>
            <div>Total</div>
            <div style={{ textAlign: 'right' }}>{clBill.reduce((s: number, c: any) => s + c.mukkadams, 0)}</div>
            <div style={{ textAlign: 'right', color: '#16a34a' }}>{fmtK(clBill.reduce((s: number, c: any) => s + c.weekly_paid, 0))}</div>
            <div style={{ textAlign: 'right', color: '#2563eb' }}>{fmtK(clBill.reduce((s: number, c: any) => s + c.settlement_paid, 0))}</div>
            <div style={{ textAlign: 'right', color: '#dc2626' }}>{fmtK(clBill.reduce((s: number, c: any) => s + c.settlement_pending, 0))}</div>
            <div style={{ textAlign: 'right', color: '#ca8a04' }}>{fmtK(clBill.reduce((s: number, c: any) => s + c.weekly_due, 0))}</div>
          </div>
        </div>
      </div>

      {/* ── Recent Weekly Payments ── */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: 14 }}>✅</span>
          <span style={{ fontSize: 13, fontWeight: 700 }}>Recent Weekly Payments</span>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {recent.map((p: any, i: number) => (
            <div key={i} style={{ background: '#fff', borderRadius: 12, padding: '12px 16px', border: '1px solid #bbf7d0', minWidth: 200, flex: '1 1 200px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div><div style={{ fontSize: 13, fontWeight: 600 }}>{p.mukkadam_name}</div><div style={{ fontSize: 11, color: '#a3a398' }}>{p.cluster_name} · {p.crew_size} crew</div></div>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#16a34a' }}>{fmt(p.amount)}</div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: '#6b6b63' }}>
                <span>{p.payment_date?.slice(5).replace('-', ' ')}</span>
                <span style={{ padding: '1px 8px', borderRadius: 5, fontSize: 10, fontWeight: 600, background: p.mode === 'UPI' ? '#ede9fe' : p.mode === 'CASH' ? '#fefce8' : '#eff6ff', color: p.mode === 'UPI' ? '#7c3aed' : p.mode === 'CASH' ? '#ca8a04' : '#2563eb' }}>{p.mode}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// WEEKLY PAY MODAL
// ─────────────────────────────────────────────────────────────────────────────

function WeeklyPayModal({ mukkadam, assignmentId, defaultDate, onClose, onSaved }: {
  mukkadam: any; assignmentId: number; defaultDate?: string;
  onClose: () => void; onSaved: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate]     = useState(defaultDate ?? today);
  const [amount, setAmount] = useState(String(mukkadam.weekly_payment_amount || ''));
  const [mode, setMode]     = useState('CASH');
  const [notes, setNotes]   = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const handleSave = async () => {
    setSaving(true); setError('');
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API_BASE_URL}/api/mukkadam-weekly-payment/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
        body: JSON.stringify({ assignment_id: assignmentId, amount, payment_date: date, mode, notes }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Failed');
      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }} onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: 16, width: 420, boxShadow: '0 20px 60px rgba(0,0,0,.2)', padding: '24px' }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>📅 Record Weekly Payment</div>
        <div style={{ fontSize: 12, color: '#a3a398', marginBottom: 20 }}>{mukkadam.mukkadam_name} · {mukkadam.crew_size} crew</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[
            { label: 'Amount (₹)',       child: <input value={amount} onChange={e => setAmount(e.target.value)} type="number" style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 14, fontFamily: 'inherit', marginTop: 4, boxSizing: 'border-box' as const }} /> },
            { label: 'Payment Date',     child: <input value={date} onChange={e => setDate(e.target.value)} type="date" style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, fontFamily: 'inherit', marginTop: 4, boxSizing: 'border-box' as const }} /> },
            { label: 'Mode',             child: <select value={mode} onChange={e => setMode(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, fontFamily: 'inherit', marginTop: 4, boxSizing: 'border-box' as const }}>{['CASH','UPI','BANK_TRANSFER','CHEQUE'].map(m => <option key={m} value={m}>{m}</option>)}</select> },
            { label: 'Notes (optional)', child: <input value={notes} onChange={e => setNotes(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 13, fontFamily: 'inherit', marginTop: 4, boxSizing: 'border-box' as const }} /> },
          ].map((field, i) => (
            <div key={i}>
              <label style={{ fontSize: 11, fontWeight: 700, color: '#6b6b63', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{field.label}</label>
              {field.child}
            </div>
          ))}
          {error && <div style={{ color: '#dc2626', fontSize: 12 }}>❌ {error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 20 }}>
          <button onClick={onClose} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e8e5de', background: '#fff', color: '#6b6b63', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: saving ? '#aaa' : '#7c3aed', color: '#fff', fontSize: 13, fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}>
            {saving ? 'Saving...' : '✓ Record Payment'}
          </button>
        </div>
      </div>
    </div>
  );
}