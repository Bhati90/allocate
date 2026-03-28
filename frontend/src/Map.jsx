import { useState, useMemo } from "react";

const F = "'Geist', system-ui, sans-serif";
const MONO = "'Geist Mono', 'SF Mono', monospace";

// ─── Urgency system ─────────────────────────────────────────────────────
function getUrgency(activities) {
  const current = activities.find(a => ["overdue","current","in_progress"].includes(a.status));
  if (!current) {
    if (activities.some(a => a.status === "done")) return { level: "done", color: "#6b7280", map: "#4b5563", fill: "#374151", label: "DONE" };
    return { level: "ok", color: "#6b7280", map: "#6b7280", fill: "#4b5563", label: "" };
  }
  if (current.status === "overdue") return { level: "overdue", color: "#dc2626", map: "#ef4444", fill: "#dc2626", label: "OVERDUE", pulse: true };
  if (current.status === "in_progress") return { level: "active", color: "#059669", map: "#10b981", fill: "#059669", label: "ACTIVE", pulse: true };
  if (current.dueDays <= 0) return { level: "today", color: "#dc2626", map: "#f97316", fill: "#ea580c", label: "TODAY", pulse: true };
  if (current.dueDays <= 3) return { level: "soon", color: "#ea580c", map: "#f97316", fill: "#c2410c", label: "DUE SOON" };
  if (current.dueDays <= 7) return { level: "week", color: "#d97706", map: "#fbbf24", fill: "#b45309", label: "THIS WEEK" };
  return { level: "ok", color: "#22c55e", map: "#22c55e", fill: "#15803d", label: "ON TRACK" };
}

const PAY = {
  paid: { color: "#16a34a", label: "Paid" },
  partial: { color: "#d97706", label: "Partial" },
  unpaid: { color: "#9ca3af", label: "Unpaid" },
};

const MUKADAMS = [
  { id: "m1", name: "Vilas Pawar", initials: "VP", color: "#2563eb", crew: 7 },
  { id: "m2", name: "Ramesh Pithe", initials: "RP", color: "#059669", crew: 10 },
  { id: "m3", name: "Hemraj Waghmare", initials: "HW", color: "#d97706", crew: 5 },
];

// ─── Farm polygons — irregular shapes like real plots ───────────────────
// Each farm has a polygon defined relative to a center point, scaled by acres
function generatePlotPolygon(seed, acres) {
  const s = (n) => { seed = (seed * 16807 + n) % 2147483647; return (seed % 1000) / 1000; };
  const sides = 4 + Math.floor(s(1) * 4); // 4-7 sides
  const scale = Math.sqrt(acres) * 12;
  const points = [];
  for (let i = 0; i < sides; i++) {
    const angle = (i / sides) * Math.PI * 2 + s(i) * 0.5;
    const r = scale * (0.6 + s(i + 10) * 0.5);
    points.push([Math.cos(angle) * r, Math.sin(angle) * r]);
  }
  return points;
}

const FARMERS = [
  {
    id: "f1", name: "Machindra Baburao Shete", plot: "77322", location: "Golegaon, Junnar",
    crop: "Crimson", totalAcres: 4.2, totalValue: 208250, advance: 45000, balance: 166650, payStatus: "partial",
    activities: [
      { name: "Pruning (छाटणी)", status: "current", acres: 4.2, deadline: "Mar 28", dueDays: 0, team: { name: "Vilas Pawar", initials: "VP", color: "#2563eb" } },
      { name: "Shoot Selection (विरळणी)", status: "upcoming", deadline: "Apr 15", dueDays: 18 },
      { name: "1st Lateral Removal", status: "upcoming" }, { name: "Shenda Stopping", status: "upcoming" },
      { name: "2nd Lateral Removal", status: "upcoming" }, { name: "Subcane", status: "upcoming" },
      { name: "Subcane", status: "upcoming" }, { name: "Hand Pasting", status: "upcoming" },
      { name: "Extra Leaf Removal", status: "upcoming" },
    ],
    cx: 420, cy: 195,
  },
  {
    id: "f2", name: "Sachin Kisan Thorat", plot: "77374", location: "Narayangaon",
    crop: "Grapes", totalAcres: 3.0, totalValue: 84000, advance: 0, balance: 84000, payStatus: "unpaid",
    activities: [{ name: "Pruning (छाटणी)", status: "current", acres: 3.0, deadline: "Mar 31", dueDays: 3, team: null }],
    cx: 340, cy: 250,
  },
  {
    id: "f3", name: "Shankar Nana Dhavle", plot: "77323", location: "Narayangaon",
    crop: "—", totalAcres: 2.5, totalValue: 62500, advance: 0, balance: 62500, payStatus: "unpaid",
    activities: [{ name: "Pruning (छाटणी)", status: "overdue", acres: 2.5, deadline: "Mar 20", dueDays: -8, team: null }],
    cx: 280, cy: 170,
  },
  {
    id: "f4", name: "Rahul Shete", plot: "77313", location: "Narayangaon",
    crop: "Crimson", totalAcres: 3.0, totalValue: 120000, advance: 30000, balance: 90000, payStatus: "partial",
    activities: [
      { name: "Pruning (छाटणी)", status: "done", acres: 3.0, deadline: "Mar 28", dueDays: 0, team: { name: "Vilas Pawar", initials: "VP", color: "#2563eb" } },
      { name: "Shoot Selection (विरळणी)", status: "upcoming", deadline: "Apr 12", dueDays: 15 },
    ],
    cx: 380, cy: 300,
  },
  {
    id: "f5", name: "Ganesh Patil", plot: "78440", location: "Khodad",
    crop: "Crimson", totalAcres: 2.0, totalValue: 80000, advance: 80000, balance: 0, payStatus: "paid",
    activities: [{ name: "Pruning (छाटणी)", status: "in_progress", acres: 2.0, deadline: "Mar 28", dueDays: 0, team: { name: "Ramesh Pithe", initials: "RP", color: "#059669" } }],
    cx: 500, cy: 220,
  },
  {
    id: "f6", name: "Nilesh Keda Chavan", plot: "75380", location: "Satana, Nashik",
    crop: "ARA 15", totalAcres: 2.92, totalValue: 73000, advance: 0, balance: 73000, payStatus: "unpaid",
    activities: [{ name: "Pruning (छाटणी)", status: "overdue", acres: 2.92, deadline: "Feb 11", dueDays: -44, team: null }],
    cx: 190, cy: 330,
  },
  {
    id: "f7", name: "Datta Chintaman Vaman", plot: "77396", location: "Narayangaon",
    crop: "Thomson", totalAcres: 1.0, totalValue: 40000, advance: 10000, balance: 30000, payStatus: "partial",
    activities: [{ name: "Pruning (छाटणी)", status: "current", acres: 1.0, deadline: "Mar 31", dueDays: 3, team: null }],
    cx: 360, cy: 180,
  },
  {
    id: "f8", name: "Sunil Bhosale", plot: "78501", location: "Golegaon",
    crop: "Thomson", totalAcres: 1.5, totalValue: 60000, advance: 60000, balance: 0, payStatus: "paid",
    activities: [{ name: "Pruning (छाटणी)", status: "done", acres: 1.5, deadline: "Mar 26", dueDays: -2, team: { name: "Hemraj Waghmare", initials: "HW", color: "#d97706" } }],
    cx: 530, cy: 150,
  },
  {
    id: "f9", name: "Vikram Jagtap", plot: "77401", location: "Narayangaon",
    crop: "Crimson", totalAcres: 3.5, totalValue: 140000, advance: 70000, balance: 70000, payStatus: "partial",
    activities: [{ name: "Pruning (छाटणी)", status: "current", acres: 3.5, deadline: "Apr 02", dueDays: 5, team: { name: "Vilas Pawar", initials: "VP", color: "#2563eb" } }],
    cx: 450, cy: 270,
  },
  {
    id: "f10", name: "Pravin Sonawane", plot: "77388", location: "Narayangaon",
    crop: "Thomson", totalAcres: 1.8, totalValue: 72000, advance: 0, balance: 72000, payStatus: "unpaid",
    activities: [{ name: "Pruning (छाटणी)", status: "current", acres: 1.8, deadline: "Mar 29", dueDays: 1, team: null }],
    cx: 310, cy: 220,
  },
  {
    id: "f11", name: "Ajay Kulkarni", plot: "78210", location: "Khodad",
    crop: "Crimson", totalAcres: 5.0, totalValue: 200000, advance: 100000, balance: 100000, payStatus: "partial",
    activities: [
      { name: "Pruning (छाटणी)", status: "done", acres: 5.0, team: { name: "Ramesh Pithe", initials: "RP", color: "#059669" } },
      { name: "Shoot Selection (विरळणी)", status: "current", acres: 5.0, deadline: "Apr 08", dueDays: 11 },
    ],
    cx: 560, cy: 270,
  },
  {
    id: "f12", name: "Bapu Thorat", plot: "77380", location: "Narayangaon",
    crop: "Grapes", totalAcres: 2.2, totalValue: 88000, advance: 44000, balance: 44000, payStatus: "partial",
    activities: [{ name: "Pruning (छाटणी)", status: "overdue", acres: 2.2, deadline: "Mar 22", dueDays: -6, team: null }],
    cx: 250, cy: 280,
  },
];

// Precompute polygons
const FARM_POLYGONS = FARMERS.map(f => ({
  ...f,
  polygon: generatePlotPolygon(parseInt(f.plot), f.totalAcres),
}));


// ═══════════════════════════════════════════════════════════════════════
// FARMER CARD (sidebar)
// ═══════════════════════════════════════════════════════════════════════

function FarmerCard({ farmer, isSelected, onClick }) {
  const urg = getUrgency(farmer.activities);
  const current = farmer.activities.find(a => ["overdue","current","in_progress"].includes(a.status));
  const pay = PAY[farmer.payStatus];
  return (
    <div onClick={onClick} style={{
      padding: "9px 14px", cursor: "pointer",
      borderBottom: "1px solid #141428",
      background: isSelected ? "#141428" : "transparent",
      borderLeft: `3px solid ${isSelected ? urg.map : "transparent"}`,
      transition: "all 0.1s",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#ededed", fontFamily: F, lineHeight: 1.25 }}>
          {farmer.name}
        </span>
        {urg.label && (
          <span style={{
            flexShrink: 0, padding: "2px 6px", borderRadius: 4,
            fontSize: 8, fontWeight: 700, letterSpacing: "0.05em",
            background: urg.map + "20", color: urg.map, fontFamily: F,
            ...(urg.pulse ? { animation: "cp 2s infinite" } : {}),
          }}>{urg.label}</span>
        )}
      </div>
      <div style={{ display: "flex", gap: 6, marginTop: 4, fontSize: 10, color: "#5a5a7a", fontFamily: F, alignItems: "center" }}>
        <span style={{ fontFamily: MONO, fontWeight: 600, color: "#8a8aa8", fontSize: 10 }}>{farmer.totalAcres}ac</span>
        <span style={{ color: "#2a2a44" }}>·</span>
        {current?.deadline && <span style={{ color: urg.color, fontWeight: 500 }}>{current.deadline}</span>}
        {current?.deadline && <span style={{ color: "#2a2a44" }}>·</span>}
        <span style={{ color: pay.color, fontWeight: 600, fontSize: 9 }}>{pay.label}</span>
        {current?.team && (
          <>
            <span style={{ color: "#2a2a44" }}>·</span>
            <span style={{
              fontSize: 8, fontWeight: 700, color: current.team.color,
              background: current.team.color + "20", padding: "0 4px", borderRadius: 3,
            }}>{current.team.initials}</span>
          </>
        )}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════
// PLOT POPUP v2 — with actions
// ═══════════════════════════════════════════════════════════════════════

function PlotPopup({ farmer, onClose, pos }) {
  const urg = getUrgency(farmer.activities);
  const current = farmer.activities.find(a => ["overdue","current","in_progress"].includes(a.status));
  const doneCount = farmer.activities.filter(a => a.status === "done").length;
  const total = farmer.activities.length;
  const pay = PAY[farmer.payStatus];
  const openNotes = current && !current.team;

  // Position popup to not overflow
  const left = Math.min(pos.x + 24, 680 - 320);
  const top = Math.min(pos.y - 40, 500 - 400);

  return (
    <div style={{
      position: "absolute", left, top: Math.max(8, top),
      width: 310, background: "#fff", borderRadius: 12,
      boxShadow: "0 12px 40px rgba(0,0,0,0.25), 0 2px 8px rgba(0,0,0,0.1)",
      overflow: "hidden", fontFamily: F, zIndex: 200,
      border: "1px solid #e5e7eb",
    }}>
      {/* Urgency strip */}
      <div style={{ height: 3, background: urg.map, ...(urg.pulse ? { animation: "sp 2s infinite" } : {}) }} />

      {/* Header: name + meta */}
      <div style={{ padding: "10px 14px 8px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#111", lineHeight: 1.2 }}>{farmer.name}</div>
            <div style={{ fontSize: 10, color: "#9ca3af", fontFamily: MONO, marginTop: 3, display: "flex", gap: 5, flexWrap: "wrap" }}>
              <span>{farmer.plot}</span>
              <span style={{ color: "#e0e0e0" }}>|</span>
              <span>{farmer.crop}</span>
              <span style={{ color: "#e0e0e0" }}>|</span>
              <span style={{ fontWeight: 600, color: "#6b7280" }}>{farmer.totalAcres}ac</span>
              <span style={{ color: "#e0e0e0" }}>|</span>
              <span style={{ color: pay.color, fontWeight: 600 }}>{pay.label}</span>
            </div>
          </div>
          <button onClick={onClose} style={{
            width: 22, height: 22, borderRadius: 5, border: "1px solid #e5e7eb",
            background: "#f9fafb", color: "#9ca3af", fontSize: 11,
            cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0, marginLeft: 6,
          }}>×</button>
        </div>
      </div>

      {/* Current activity hero */}
      {current ? (
        <div style={{
          margin: "0 14px 8px", padding: "10px 12px", borderRadius: 8,
          background: urg.level === "overdue" ? "#fef2f2" : urg.level === "active" ? "#ecfdf3" : urg.level === "today" ? "#fff7ed" : "#fffbeb",
          border: `1px solid ${urg.level === "overdue" ? "#fecaca" : urg.level === "active" ? "#a7f3d0" : urg.level === "today" ? "#fed7aa" : "#fde68a"}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
            <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.07em", color: urg.color }}>
              {current.status === "overdue" ? "⚠ OVERDUE" : current.status === "in_progress" ? "▶ IN PROGRESS" : "● NOW"}
            </span>
            {current.dueDays !== undefined && (
              <span style={{ fontSize: 10, fontWeight: 700, color: urg.color, fontFamily: MONO }}>
                {current.dueDays < 0 ? `${Math.abs(current.dueDays)}d late` : current.dueDays === 0 ? "Today" : `${current.dueDays}d left`}
              </span>
            )}
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#111", lineHeight: 1.2 }}>{current.name}</div>
          <div style={{ display: "flex", gap: 14, marginTop: 7, fontSize: 10, color: "#374151" }}>
            <div>
              <div style={{ fontSize: 7, color: "#9ca3af", fontWeight: 600, letterSpacing: "0.07em" }}>DEADLINE</div>
              <div style={{ fontWeight: 600, fontFamily: MONO, fontSize: 11, color: urg.color }}>{current.deadline}</div>
            </div>
            <div>
              <div style={{ fontSize: 7, color: "#9ca3af", fontWeight: 600, letterSpacing: "0.07em" }}>ACRES</div>
              <div style={{ fontWeight: 600, fontSize: 11 }}>{current.acres || farmer.totalAcres}</div>
            </div>
            <div>
              <div style={{ fontSize: 7, color: "#9ca3af", fontWeight: 600, letterSpacing: "0.07em" }}>TEAM</div>
              {current.team ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                  <span style={{
                    width: 14, height: 14, borderRadius: 3, background: current.team.color,
                    color: "#fff", fontSize: 7, fontWeight: 700,
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                  }}>{current.team.initials}</span>
                  <span style={{ fontSize: 10, fontWeight: 600 }}>{current.team.name.split(" ")[0]}</span>
                </span>
              ) : (
                <span style={{ fontSize: 10, color: "#dc2626", fontWeight: 600 }}>—</span>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div style={{
          margin: "0 14px 8px", padding: "8px 12px", borderRadius: 8,
          background: "#f0fdf4", border: "1px solid #bbf7d0",
          fontSize: 11, color: "#16a34a", fontWeight: 600, textAlign: "center",
        }}>✓ Current work completed</div>
      )}

      {/* Activity progress bar */}
      <div style={{ padding: "0 14px 8px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontSize: 8, fontWeight: 600, color: "#9ca3af", letterSpacing: "0.06em" }}>ACTIVITIES</span>
          <span style={{ fontSize: 9, color: "#6b7280", fontFamily: MONO }}>{doneCount}/{total}</span>
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          {farmer.activities.map((a, i) => (
            <div key={i} title={a.name} style={{
              flex: 1, height: 4, borderRadius: 2,
              background: a.status === "done" ? "#22c55e" : a.status === "in_progress" ? "#0891b2"
                : a.status === "current" ? "#f59e0b" : a.status === "overdue" ? "#ef4444" : "#e5e7eb",
              ...(a.status === "in_progress" ? { animation: "sp 1.5s infinite" } : {}),
            }} />
          ))}
        </div>
      </div>

      {/* ─── ACTIONS BAR ─── */}
      <div style={{
        padding: "8px 14px",
        borderTop: "1px solid #f3f4f6",
        display: "flex", gap: 4, flexWrap: "wrap",
      }}>
        {!current?.team && current && (
          <button style={{
            ...actionBtn, background: "#111", color: "#fff", borderColor: "#111", flex: 1,
          }}>Allocate →</button>
        )}
        {current?.team && current?.status !== "done" && (
          <button style={{
            ...actionBtn, background: "#059669", color: "#fff", borderColor: "#059669",
          }}>✓ Complete</button>
        )}
        <button style={actionBtn}>↔ Move</button>
        <button style={actionBtn}>📝 Note</button>
        <button style={{ ...actionBtn, color: "#dc2626", borderColor: "#fecaca" }}>Cancel</button>
      </div>

      {/* Financial footer */}
      <div style={{
        padding: "6px 14px", borderTop: "1px solid #f3f4f6",
        background: "#fafafa", display: "flex", justifyContent: "space-between",
        fontSize: 9, color: "#9ca3af",
      }}>
        <span>Total ₹{(farmer.totalValue / 1000).toFixed(1)}K</span>
        <span style={{ color: farmer.balance > 0 ? "#d97706" : "#16a34a" }}>
          Bal ₹{(farmer.balance / 1000).toFixed(1)}K
        </span>
        <span style={{ fontFamily: MONO }}>Plot {farmer.plot}</span>
      </div>
    </div>
  );
}

const actionBtn = {
  padding: "5px 10px", borderRadius: 5, border: "1px solid #e5e7eb",
  background: "#fff", fontSize: 10, fontWeight: 600, cursor: "pointer",
  fontFamily: F, color: "#374151",
};


// ═══════════════════════════════════════════════════════════════════════
// SVG MAP WITH POLYGON PLOTS
// ═══════════════════════════════════════════════════════════════════════

function FarmMap({ farms, selectedId, onSelect }) {
  return (
    <svg viewBox="0 0 700 500" style={{ width: "100%", height: "100%", background: "#0a0a18" }}>
      <defs>
        {/* Glow filter for urgent plots */}
        <filter id="glow-red" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feFlood floodColor="#ef4444" floodOpacity="0.4" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="shadow" />
          <feMerge><feMergeNode in="shadow" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="glow-orange" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feFlood floodColor="#f97316" floodOpacity="0.35" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="shadow" />
          <feMerge><feMergeNode in="shadow" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="glow-green" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feFlood floodColor="#10b981" floodOpacity="0.3" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="shadow" />
          <feMerge><feMergeNode in="shadow" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="selected-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feFlood floodColor="#ffffff" floodOpacity="0.3" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="shadow" />
          <feMerge><feMergeNode in="shadow" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Terrain: roads */}
      <path d="M 50,250 Q 150,240 300,245 T 650,255" stroke="#1a1a30" strokeWidth="2.5" fill="none" />
      <path d="M 300,50 Q 310,150 320,250 T 340,450" stroke="#1a1a30" strokeWidth="2" fill="none" />
      <path d="M 100,120 Q 200,130 350,125 T 600,140" stroke="#151528" strokeWidth="1.5" fill="none" />
      <path d="M 150,380 Q 280,370 400,375 T 600,360" stroke="#151528" strokeWidth="1.5" fill="none" />
      {/* Dashed highway */}
      <path d="M 80,430 Q 250,350 400,320 T 660,180" stroke="#25254a" strokeWidth="1" fill="none" strokeDasharray="8,5" />

      {/* Town labels */}
      <text x="300" y="80" fill="#1e1e3a" fontSize="11" fontFamily={F} fontWeight="600">Narayangaon</text>
      <text x="490" y="180" fill="#1e1e3a" fontSize="10" fontFamily={F}>Khodad</text>
      <text x="150" y="360" fill="#1e1e3a" fontSize="10" fontFamily={F}>Satana</text>
      <text x="430" y="340" fill="#1e1e3a" fontSize="10" fontFamily={F}>Golegaon</text>
      <text x="90" y="460" fill="#1e1e3a" fontSize="11" fontFamily={F} fontWeight="600">Junnar</text>

      {/* Farm polygons */}
      {farms.map(farm => {
        const urg = getUrgency(farm.activities);
        const isSel = selectedId === farm.id;
        const pts = farm.polygon.map(([dx, dy]) => `${farm.cx + dx},${farm.cy + dy}`).join(" ");
        
        const glowFilter = isSel ? "url(#selected-glow)"
          : urg.level === "overdue" ? "url(#glow-red)"
          : urg.level === "today" || urg.level === "soon" ? "url(#glow-orange)"
          : urg.level === "active" ? "url(#glow-green)"
          : "none";

        return (
          <g key={farm.id} onClick={() => onSelect(farm.id)} style={{ cursor: "pointer" }}>
            {/* Pulse ring for urgent */}
            {urg.pulse && !isSel && (
              <polygon
                points={pts}
                fill="none" stroke={urg.map} strokeWidth="1.5"
                opacity="0.4"
              >
                <animate attributeName="stroke-width" values="1;3;1" dur="2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.4;0.1;0.4" dur="2s" repeatCount="indefinite" />
              </polygon>
            )}
            {/* Main polygon */}
            <polygon
              points={pts}
              fill={isSel ? urg.map : urg.fill}
              fillOpacity={isSel ? 0.7 : (urg.level === "done" ? 0.25 : 0.55)}
              stroke={isSel ? "#fff" : urg.map}
              strokeWidth={isSel ? 2 : 1}
              strokeOpacity={isSel ? 1 : 0.7}
              filter={glowFilter}
              style={{ transition: "fill-opacity 0.15s, stroke-width 0.15s" }}
            />
            {/* Acres label inside polygon (only for larger plots) */}
            {farm.totalAcres >= 2 && (
              <text
                x={farm.cx} y={farm.cy + 1}
                textAnchor="middle" dominantBaseline="middle"
                fill={isSel ? "#fff" : urg.map}
                fillOpacity={isSel ? 1 : 0.8}
                fontSize={farm.totalAcres >= 4 ? 9 : 7.5}
                fontWeight="700" fontFamily={MONO}
                style={{ pointerEvents: "none" }}
              >
                {farm.totalAcres}
              </text>
            )}
          </g>
        );
      })}

      {/* Legend */}
      <g transform="translate(560, 400)">
        <rect x="0" y="0" width="125" height="90" rx="6" fill="#0a0a18" fillOpacity="0.85" stroke="#1a1a30" />
        <text x="10" y="15" fill="#3a3a5a" fontSize="7" fontWeight="700" letterSpacing="0.08em" fontFamily={F}>TIME URGENCY</text>
        {[
          { color: "#ef4444", label: "Overdue" },
          { color: "#f97316", label: "Due soon" },
          { color: "#fbbf24", label: "This week" },
          { color: "#22c55e", label: "On track / Active" },
          { color: "#4b5563", label: "Completed" },
        ].map((l, i) => (
          <g key={i} transform={`translate(10, ${26 + i * 12})`}>
            <rect x="0" y="0" width="10" height="7" rx="1.5" fill={l.color} fillOpacity="0.65" stroke={l.color} strokeWidth="0.5" />
            <text x="16" y="6.5" fill="#5a5a7a" fontSize="7.5" fontFamily={F}>{l.label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}


// ═══════════════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════════════

export default function BookingPlotMapV2() {
  const [selectedId, setSelectedId] = useState(null);
  const [search, setSearch] = useState("");

  const selected = FARM_POLYGONS.find(f => f.id === selectedId);

  const filtered = search
    ? FARM_POLYGONS.filter(f => f.name.toLowerCase().includes(search.toLowerCase()) || f.plot.includes(search))
    : FARM_POLYGONS;

  const sorted = [...filtered].sort((a, b) => {
    const order = { overdue: 0, today: 1, active: 2, soon: 3, week: 4, ok: 5, done: 6 };
    return (order[getUrgency(a.activities).level] || 5) - (order[getUrgency(b.activities).level] || 5);
  });

  const overdueN = FARMERS.filter(f => getUrgency(f.activities).level === "overdue").length;
  const todayN = FARMERS.filter(f => ["today","active"].includes(getUrgency(f.activities).level)).length;
  const unassignedN = FARMERS.filter(f => {
    const c = f.activities.find(a => ["overdue","current","in_progress"].includes(a.status));
    return c && !c.team;
  }).length;

  return (
    <div style={{ fontFamily: F, background: "#0a0a18", height: "100vh", display: "flex", flexDirection: "column", color: "#ededed" }}>
      <link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
      <style>{`
        @keyframes cp { 0%,100%{opacity:1} 50%{opacity:.4} }
        @keyframes sp { 0%,100%{opacity:1} 50%{opacity:.3} }
        * { box-sizing:border-box; margin:0 }
        ::-webkit-scrollbar{width:4px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:#1a1a30;border-radius:2px}
      `}</style>

      {/* Top bar */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "8px 18px", borderBottom: "1px solid #141428",
        background: "rgba(10,10,24,0.95)", backdropFilter: "blur(8px)", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 700 }}>📍 Plot Map</span>
          <span style={{ fontSize: 10, color: "#3a3a5a" }}>Narayangaon Pune · Pruning</span>
        </div>
        <div style={{ display: "flex", gap: 6, fontSize: 10 }}>
          {overdueN > 0 && <span style={{ padding: "2px 8px", borderRadius: 4, background: "#dc262618", color: "#ef4444", fontWeight: 600, fontFamily: MONO }}>{overdueN} overdue</span>}
          {todayN > 0 && <span style={{ padding: "2px 8px", borderRadius: 4, background: "#f9731618", color: "#fb923c", fontWeight: 600, fontFamily: MONO }}>{todayN} today</span>}
          {unassignedN > 0 && <span style={{ padding: "2px 8px", borderRadius: 4, background: "#fbbf2418", color: "#fbbf24", fontWeight: 600, fontFamily: MONO }}>{unassignedN} no team</span>}
          <span style={{ padding: "2px 8px", borderRadius: 4, background: "#141428", color: "#5a5a7a", fontFamily: MONO }}>{FARMERS.length} plots</span>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Sidebar */}
        <div style={{ width: 270, borderRight: "1px solid #141428", display: "flex", flexDirection: "column", flexShrink: 0 }}>
          <div style={{ padding: "8px 12px", borderBottom: "1px solid #141428" }}>
            <input
              placeholder="Search farmer, plot..."
              value={search} onChange={e => setSearch(e.target.value)}
              style={{
                width: "100%", padding: "6px 10px", borderRadius: 6,
                border: "1px solid #141428", background: "#0e0e22",
                color: "#a0a0c0", fontSize: 11, fontFamily: F, outline: "none",
              }}
            />
          </div>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {sorted.map(f => (
              <FarmerCard key={f.id} farmer={f} isSelected={selectedId === f.id}
                onClick={() => setSelectedId(selectedId === f.id ? null : f.id)} />
            ))}
          </div>
        </div>

        {/* Map */}
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          <FarmMap
            farms={FARM_POLYGONS}
            selectedId={selectedId}
            onSelect={id => setSelectedId(selectedId === id ? null : id)}
          />
          {/* Popup */}
          {selected && (
            <PlotPopup
              farmer={selected}
              onClose={() => setSelectedId(null)}
              pos={{ x: selected.cx, y: selected.cy }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
