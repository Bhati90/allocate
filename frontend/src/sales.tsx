// SalesPerformance.tsx
// Drop this component into your Plan tab alongside AgroIntelUnified
// Usage in TenderDashboard: import SalesPerformance from './SalesPerformance';
// Then add <SalesPerformance /> inside the tab === 'plan' block

import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from './types/config';

// ── Colour helpers ─────────────────────────────────────────────────
const SEVERITY_COLORS: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  green:       { bg: '#f0fdf4', border: '#bbf7d0', text: '#15803d', badge: '#dcfce7' },
  lime:        { bg: '#f7fee7', border: '#d9f99d', text: '#3f6212', badge: '#ecfccb' },
  yellow:      { bg: '#fefce8', border: '#fde047', text: '#854d0e', badge: '#fef9c3' },
  gold:        { bg: '#fffbeb', border: '#fcd34d', text: '#92400e', badge: '#fef3c7' },
  orange:      { bg: '#fff7ed', border: '#fed7aa', text: '#c2410c', badge: '#ffedd5' },
  deep_orange: { bg: '#fff4ed', border: '#fdba74', text: '#9a3412', badge: '#ffe4cc' },
  red:         { bg: '#fef2f2', border: '#fecaca', text: '#dc2626', badge: '#fee2e2' },
  critical:    { bg: '#fef2f2', border: '#f87171', text: '#7f1d1d', badge: '#fca5a5' },
};

const pctColor = (v: number, good = 70, mid = 40) =>
  v >= good ? '#16a34a' : v >= mid ? '#f59e0b' : '#ef4444';

const pctBg = (v: number, good = 70, mid = 40) =>
  v >= good ? '#f0fdf4' : v >= mid ? '#fefce8' : '#fef2f2';

const fmt = (n: number) =>
  n >= 100000 ? `₹${(n / 100000).toFixed(1)}L` : n >= 1000 ? `₹${(n / 1000).toFixed(1)}k` : `₹${n}`;

// ── Sub-tabs ───────────────────────────────────────────────────────
type SubTab = 'overview' | 'weekly' | 'clusters' | 'heatmap' | 'farmers';

export default function SalesPerformance({ onKpisReady }: { onKpisReady?: (kpis: any) => void }) {
  const [data, setData]       = useState<any>(null);
  const [loading, setLoading] = useState(false);
  
  const [subTab, setSubTab]   = useState<SubTab>('overview');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo]     = useState('');
  const [clusterId, setClusterId] = useState('');
  const [clusters, setClusters]   = useState<any[]>([]);
  const [sortFarmer, setSortFarmer] = useState<'ot' | 'avg' | 'total'>('ot');
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null);

  // Load cluster list for filter
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/clusters/`)
      .then(r => r.json())
      .then(d => setClusters(Array.isArray(d) ? d : d.results ?? []))
      .catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const params = new URLSearchParams();
      if (clusterId) params.set('cluster_id', clusterId);
      if (dateFrom)  params.set('date_from', dateFrom);
      if (dateTo)    params.set('date_to', dateTo);
      const res = await fetch(`${API_BASE_URL}/api/sales-performance/?${params}`, {
        headers: { Authorization: `Token ${token}` },
      });
      const d = await res.json();
      setData(d);
      if (onKpisReady && d?.kpis) onKpisReady(d.kpis);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [clusterId, dateFrom, dateTo]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <div style={{ fontFamily: 'inherit' }}>
      {/* ── Header + filters ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 800, color: '#1a1a1a' }}>📊 Sales Date Performance</div>
          <div style={{ fontSize: 11, color: '#a3a398', marginTop: 2 }}>
            How quickly completed activities were delivered vs. their sales date
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select value={clusterId} onChange={e => setClusterId(e.target.value)}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 12, background: '#fff', color: '#1a1a1a', fontFamily: 'inherit' }}>
            <option value="">All Clusters</option>
            {clusters.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 12, background: '#fff', fontFamily: 'inherit' }} />
          <span style={{ color: '#a3a398', fontSize: 11 }}>–</span>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #e8e5de', fontSize: 12, background: '#fff', fontFamily: 'inherit' }} />
          {(dateFrom || dateTo) && (
            <button onClick={() => { setDateFrom(''); setDateTo(''); }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#a3a398', fontSize: 13 }}>✕</button>
          )}
          <button onClick={fetchData}
            style={{ padding: '6px 14px', borderRadius: 8, background: '#16a34a', color: '#fff', border: 'none', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>
            ↻ Refresh
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '64px 0' }}>
          <div style={{ width: 28, height: 28, border: '3px solid #e8e5de', borderTopColor: '#16a34a', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      )}

      {!loading && data && data.counted === 0 && (
        <div style={{ textAlign: 'center', padding: '64px 0', color: '#a3a398', fontSize: 14 }}>
          No completed activities found for the selected filters.
        </div>
      )}

      {!loading && data && data.counted > 0 && (() => {
        const { kpis, buckets, rollup, weekly_trend, cluster_breakdown,
                activity_heatmap, activities_list, farmer_performance } = data;

        // ── Sub-tab pills ──
        const SUBTABS: { key: SubTab; label: string }[] = [
          { key: 'overview', label: '📊 Overview' },
          { key: 'weekly',   label: '📈 Weekly Trend' },
          { key: 'clusters', label: '🏘 Clusters' },
          { key: 'heatmap',  label: '🔥 Activity Heat Map' },
          { key: 'farmers',  label: '👨‍🌾 Farmers' },
        ];

        return (
          <>
            {/* Sub-tab pills */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
              {SUBTABS.map(t => (
                <button key={t.key} onClick={() => setSubTab(t.key)}
                  style={{ padding: '7px 16px', borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                    border: `1px solid ${subTab === t.key ? '#16a34a' : '#e8e5de'}`,
                    background: subTab === t.key ? '#f0fdf4' : '#fff',
                    color: subTab === t.key ? '#16a34a' : '#6b6b63' }}>
                  {t.label}
                </button>
              ))}
              <span style={{ marginLeft: 'auto', fontSize: 11, color: '#a3a398', alignSelf: 'center' }}>
                {data.counted} activities · {data.total_area} ac
              </span>
            </div>

            {/* ══ OVERVIEW ══ */}
            {subTab === 'overview' && (
              <>
                {/* KPI strip */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10, marginBottom: 20 }}>
                  {[
                    { label: 'On Time %',        val: `${kpis.on_time_pct}%`,       good: 70, mid: 40 },
                    { label: '≤ 3d %',           val: `${kpis.within_3d_pct}%`,     good: 85, mid: 60 },
                    { label: 'On Time % (area)', val: `${kpis.on_time_area_pct}%`,  good: 70, mid: 40 },
                    { label: '≤ 3d % (area)',    val: `${kpis.w3_area_pct}%`,       good: 85, mid: 60 },
                    { label: 'Avg Days Late',    val: `${kpis.avg_days_late}d`,     good: -1, mid: -1 },
                    { label: 'Activities',       val: kpis.total_activities,        good: -1, mid: -1 },
                    { label: 'Total Area',       val: `${kpis.total_area} ac`,      good: -1, mid: -1 },
                  ].map((k, i) => (
                    <div key={i} style={{ background: '#fff', borderRadius: 12, padding: '14px 16px', border: '1px solid #e8e5de', textAlign: 'center' }}>
                      <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.1,
                        color: k.good > 0 ? pctColor(parseFloat(String(k.val)), k.good, k.mid) : '#1a1a1a' }}>
                        {k.val}
                      </div>
                      <div style={{ fontSize: 10, color: '#6b6b63', fontWeight: 600, marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        {k.label}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Granular bucket table */}
                <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden', marginBottom: 20 }}>
                  <div style={{ padding: '12px 16px', borderBottom: '1px solid #e8e5de', fontSize: 13, fontWeight: 700, color: '#1a1a1a' }}>
                    Day-Level Breakdown
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '2fr 80px 80px 100px 110px 120px', padding: '8px 16px', fontSize: 10, fontWeight: 700, color: '#a3a398', textTransform: 'uppercase', letterSpacing: '0.05em', background: '#fafaf8', borderBottom: '1px solid #e8e5de' }}>
                    <div>Bucket</div>
                    <div style={{ textAlign: 'right' }}>Count</div>
                    <div style={{ textAlign: 'right' }}>% Share</div>
                    <div style={{ textAlign: 'right' }}>Avg Days</div>
                    <div style={{ textAlign: 'right' }}>Area (ac)</div>
                    <div style={{ textAlign: 'right' }}>Area-Wtd Avg</div>
                  </div>
                  {buckets.map((b: any) => {
                    const sc = SEVERITY_COLORS[b.severity] ?? SEVERITY_COLORS.red;
                    const barWidth = data.counted > 0 ? (b.count / data.counted) * 100 : 0;
                    return (
                      <div key={b.key} style={{ display: 'grid', gridTemplateColumns: '2fr 80px 80px 100px 110px 120px', padding: '10px 16px', borderBottom: '1px solid #f0ede7', background: sc.bg, alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: sc.text }}>{b.label}</span>
                          <div style={{ flex: 1, background: '#e8e5de', borderRadius: 3, height: 6, maxWidth: 120, overflow: 'hidden' }}>
                            <div style={{ width: `${barWidth}%`, height: '100%', background: sc.text, borderRadius: 3 }} />
                          </div>
                        </div>
                        <div style={{ textAlign: 'right', fontWeight: 700, color: sc.text }}>{b.count}</div>
                        <div style={{ textAlign: 'right', color: sc.text }}>{b.pct}%</div>
                        <div style={{ textAlign: 'right', color: '#6b6b63' }}>{b.avg_days}d</div>
                        <div style={{ textAlign: 'right', color: '#6b6b63' }}>{b.area_ac}</div>
                        <div style={{ textAlign: 'right', color: '#6b6b63' }}>{b.area_wtd_avg}d</div>
                      </div>
                    );
                  })}
                  {/* Total row */}
                  <div style={{ display: 'grid', gridTemplateColumns: '2fr 80px 80px 100px 110px 120px', padding: '10px 16px', background: '#f5f4ef', borderTop: '2px solid #e8e5de', fontWeight: 700, fontSize: 13 }}>
                    <div>Total</div>
                    <div style={{ textAlign: 'right' }}>{data.counted}</div>
                    <div style={{ textAlign: 'right' }}>100%</div>
                    <div style={{ textAlign: 'right', color: '#6b6b63' }}>{kpis.avg_days_late}d</div>
                    <div style={{ textAlign: 'right', color: '#6b6b63' }}>{data.total_area}</div>
                    <div />
                  </div>
                </div>

                {/* Roll-up */}
                <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden' }}>
                  <div style={{ padding: '12px 16px', borderBottom: '1px solid #e8e5de', fontSize: 13, fontWeight: 700 }}>Range Roll-Up</div>
                  <div style={{ display: 'flex', gap: 0 }}>
                    {rollup.map((r: any, i: number) => {
                      const sc = SEVERITY_COLORS[r.severity] ?? SEVERITY_COLORS.red;
                      const w = data.counted > 0 ? (r.count / data.counted) * 100 : 0;
                      return (
                        <div key={r.key} title={`${r.label}: ${r.count} (${r.pct}%)`}
                          style={{ flex: w, minWidth: w > 0 ? 4 : 0, background: sc.text, height: 28, position: 'relative', overflow: 'hidden', borderRight: i < rollup.length - 1 ? '1px solid rgba(255,255,255,0.3)' : 'none' }}>
                          {w > 8 && (
                            <span style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: '#fff', whiteSpace: 'nowrap' }}>
                              {r.pct}%
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <div style={{ display: 'flex', gap: 12, padding: '10px 16px', flexWrap: 'wrap' }}>
                    {rollup.map((r: any) => {
                      const sc = SEVERITY_COLORS[r.severity] ?? SEVERITY_COLORS.red;
                      return (
                        <span key={r.key} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11 }}>
                          <span style={{ width: 10, height: 10, borderRadius: 2, background: sc.text, display: 'inline-block', flexShrink: 0 }} />
                          <span style={{ color: '#6b6b63' }}>{r.label}:</span>
                          <span style={{ fontWeight: 700, color: sc.text }}>{r.count} ({r.pct}%)</span>
                        </span>
                      );
                    })}
                  </div>
                </div>
              </>
            )}

            {/* ══ WEEKLY TREND ══ */}
            {subTab === 'weekly' && (
              <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid #e8e5de', fontSize: 13, fontWeight: 700 }}>
                  Week-over-Week Performance (cohort by Sales Date week)
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: '#fafaf8' }}>
                        {['Week', 'Activities', 'On Time', 'OT %', '≤ 3d', '≤3d %', 'Avg Days Late', 'Area (ac)', 'OT % (area)', 'WoW Δ OT%', 'WoW Δ ≤3d%'].map((h, i) => (
                          <th key={i} style={{ padding: '10px 12px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#a3a398', textAlign: i > 0 ? 'right' : 'left', borderBottom: '2px solid #e8e5de', whiteSpace: 'nowrap' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {weekly_trend.map((w: any, i: number) => (
                        <tr key={w.week_start} style={{ background: i % 2 === 0 ? '#fafaf8' : '#fff', borderBottom: '1px solid #f0ede7' }}>
                          <td style={{ padding: '9px 12px', fontWeight: 600, color: '#374151' }}>{w.week_label}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#6b6b63' }}>{w.total}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#16a34a', fontWeight: 600 }}>{w.on_time}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                              background: pctBg(w.on_time_pct), color: pctColor(w.on_time_pct) }}>
                              {w.on_time_pct}%
                            </span>
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#16a34a' }}>{w.within_3d}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                              background: pctBg(w.within_3d_pct, 85, 60), color: pctColor(w.within_3d_pct, 85, 60) }}>
                              {w.within_3d_pct}%
                            </span>
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: w.avg_days_late > 7 ? '#dc2626' : '#6b6b63', fontWeight: w.avg_days_late > 7 ? 700 : 400 }}>{w.avg_days_late}d</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#6b6b63' }}>{w.area_ac}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                              background: pctBg(w.on_time_area_pct), color: pctColor(w.on_time_area_pct) }}>
                              {w.on_time_area_pct}%
                            </span>
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', fontWeight: 700,
                            color: w.wow_ot === null ? '#a3a398' : w.wow_ot >= 0 ? '#16a34a' : '#dc2626' }}>
                            {w.wow_ot === null ? '—' : `${w.wow_ot >= 0 ? '+' : ''}${w.wow_ot}pp`}
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', fontWeight: 700,
                            color: w.wow_w3 === null ? '#a3a398' : w.wow_w3 >= 0 ? '#16a34a' : '#dc2626' }}>
                            {w.wow_w3 === null ? '—' : `${w.wow_w3 >= 0 ? '+' : ''}${w.wow_w3}pp`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ══ CLUSTERS ══ */}
            {subTab === 'clusters' && (
              <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid #e8e5de', fontSize: 13, fontWeight: 700 }}>Per-Cluster Breakdown</div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: '#fafaf8' }}>
                        {['Cluster', 'Total', 'On Time', '1–3d', '4–6d', '7–10d', '11–15d', '16–30d', '30d+', 'OT %', '≤3d %', 'Area (ac)', 'OT % (area)'].map((h, i) => (
                          <th key={i} style={{ padding: '10px 12px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#a3a398', textAlign: i === 0 ? 'left' : 'right', borderBottom: '2px solid #e8e5de', whiteSpace: 'nowrap' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {cluster_breakdown.map((c: any, i: number) => (
                        <tr key={c.cluster}
                          style={{ background: expandedCluster === c.cluster ? '#fafaf8' : i % 2 === 0 ? '#fafaf8' : '#fff', borderBottom: '1px solid #f0ede7', cursor: 'pointer' }}
                          onClick={() => setExpandedCluster(expandedCluster === c.cluster ? null : c.cluster)}>
                          <td style={{ padding: '9px 12px', fontWeight: 700, color: '#1a1a1a' }}>
                            <span style={{ fontSize: 9, color: '#a3a398', marginRight: 5 }}>
                              {expandedCluster === c.cluster ? '▲' : '▼'}
                            </span>
                            {c.cluster}
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', fontWeight: 700 }}>{c.total}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#16a34a', fontWeight: 600 }}>{c.on_time}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#3f6212' }}>{c.late_1_3d}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#c2410c' }}>{c.late_4_6d}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#9a3412' }}>{c.late_7_10d}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#dc2626' }}>{c.late_11_15d}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#dc2626' }}>{c.late_16_30d}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#7f1d1d', fontWeight: 700 }}>{c.late_30p}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: pctBg(c.on_time_pct), color: pctColor(c.on_time_pct) }}>{c.on_time_pct}%</span>
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: pctBg(c.within_3d_pct, 85, 60), color: pctColor(c.within_3d_pct, 85, 60) }}>{c.within_3d_pct}%</span>
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#6b6b63' }}>{c.area_ac}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: pctBg(c.on_time_area_pct), color: pctColor(c.on_time_area_pct) }}>{c.on_time_area_pct}%</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ══ ACTIVITY HEAT MAP ══ */}
            {subTab === 'heatmap' && (
              <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid #e8e5de', fontSize: 13, fontWeight: 700 }}>
                  Cluster × Activity — On-Time % Heat Map
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 600 }}>
                    <thead>
                      <tr style={{ background: '#fafaf8' }}>
                        <th style={{ padding: '10px 14px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#a3a398', textAlign: 'left', borderBottom: '2px solid #e8e5de', whiteSpace: 'nowrap', minWidth: 160 }}>
                          Cluster
                        </th>
                        {activities_list.map((act: string) => (
                          <th key={act} style={{ padding: '10px 10px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#a3a398', textAlign: 'center', borderBottom: '2px solid #e8e5de', whiteSpace: 'nowrap' }}>
                            {act}
                          </th>
                        ))}
                        <th style={{ padding: '10px 12px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#a3a398', textAlign: 'center', borderBottom: '2px solid #e8e5de', whiteSpace: 'nowrap' }}>
                          Overall OT%
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {activity_heatmap.map((row: any, i: number) => (
                        <tr key={row.cluster} style={{ background: i % 2 === 0 ? '#fafaf8' : '#fff', borderBottom: '1px solid #f0ede7' }}>
                          <td style={{ padding: '9px 14px', fontWeight: 700, color: '#1a1a1a' }}>{row.cluster}</td>
                          {activities_list.map((act: string) => {
                            const s = row.activities[act];
                            if (!s || s.pct === null) return (
                              <td key={act} style={{ padding: '9px 10px', textAlign: 'center', color: '#d1d5db', fontSize: 11 }}>—</td>
                            );
                            return (
                              <td key={act} style={{ padding: '6px 10px', textAlign: 'center' }}>
                                <div style={{ padding: '3px 8px', borderRadius: 8, fontSize: 11, fontWeight: 700,
                                  background: pctBg(s.pct), color: pctColor(s.pct), display: 'inline-block' }}>
                                  {s.pct}%
                                  <span style={{ fontSize: 9, fontWeight: 400, color: 'inherit', opacity: 0.7, marginLeft: 3 }}>({s.total})</span>
                                </div>
                              </td>
                            );
                          })}
                          <td style={{ padding: '6px 12px', textAlign: 'center' }}>
                            <span style={{ padding: '3px 10px', borderRadius: 8, fontSize: 12, fontWeight: 800,
                              background: pctBg(row.overall_ot_pct), color: pctColor(row.overall_ot_pct), display: 'inline-block' }}>
                              {row.overall_ot_pct}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ══ FARMERS ══ */}
            {subTab === 'farmers' && (
              <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e8e5de', overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid #e8e5de' }}>
                  <span style={{ fontSize: 13, fontWeight: 700 }}>Farmer-Level Performance</span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {([['ot', 'Sort: OT%'], ['avg', 'Sort: Avg Days'], ['total', 'Sort: Total']] as const).map(([k, l]) => (
                      <button key={k} onClick={() => setSortFarmer(k)}
                        style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                          border: `1px solid ${sortFarmer === k ? '#16a34a' : '#e8e5de'}`,
                          background: sortFarmer === k ? '#f0fdf4' : '#fff',
                          color: sortFarmer === k ? '#16a34a' : '#6b6b63' }}>
                        {l}
                      </button>
                    ))}
                  </div>
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: '#fafaf8' }}>
                        {['Farmer', 'Cluster(s)', 'Activities', 'On Time', 'OT %', '≤ 3d', '≤3d %', 'Avg Days Late', 'Area (ac)', 'Late Area'].map((h, i) => (
                          <th key={i} style={{ padding: '10px 12px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#a3a398', textAlign: i < 2 ? 'left' : 'right', borderBottom: '2px solid #e8e5de', whiteSpace: 'nowrap' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[...farmer_performance].sort((a: any, b: any) => {
                        if (sortFarmer === 'ot')    return a.on_time_pct - b.on_time_pct;
                        if (sortFarmer === 'avg')   return b.avg_days_late - a.avg_days_late;
                        if (sortFarmer === 'total') return b.total - a.total;
                        return 0;
                      }).map((f: any, i: number) => (
                        <tr key={f.farmer} style={{ background: i % 2 === 0 ? '#fafaf8' : '#fff', borderBottom: '1px solid #f0ede7' }}>
                          <td style={{ padding: '9px 12px', fontWeight: 700, color: '#1a1a1a' }}>{f.farmer}</td>
                          <td style={{ padding: '9px 12px', color: '#6b6b63', fontSize: 11 }}>{f.clusters.join(', ')}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#6b6b63' }}>{f.total}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#16a34a', fontWeight: 600 }}>{f.on_time}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: pctBg(f.on_time_pct), color: pctColor(f.on_time_pct) }}>{f.on_time_pct}%</span>
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#16a34a' }}>{f.within_3d}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: pctBg(f.within_3d_pct, 85, 60), color: pctColor(f.within_3d_pct, 85, 60) }}>{f.within_3d_pct}%</span>
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', fontWeight: 700,
                            color: f.avg_days_late > 7 ? '#dc2626' : f.avg_days_late > 3 ? '#f59e0b' : '#16a34a' }}>
                            {f.avg_days_late}d
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: '#6b6b63' }}>{f.area_ac}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', fontWeight: 700,
                            color: f.late_area > 10 ? '#dc2626' : f.late_area > 0 ? '#f59e0b' : '#16a34a' }}>
                            {f.late_area > 0 ? `${f.late_area} ac` : '✓'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        );
      })()}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}