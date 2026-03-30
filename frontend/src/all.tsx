import { useState, useEffect, useCallback } from "react";
import { Search, Users, User, ChevronRight, Loader2, AlertCircle, RefreshCw, MapPin, Phone, Layers, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import FarmerProfile from "./Farmer";
import MukkadamProfile from "./Mukadam";

const API_BASE = "http://localhost:8002/tender";

// ─── Types ────────────────────────────────────────────────────────────────────
interface FarmerRow {
  farmer_id: string;
  farmer_name: string;
  phone_number: string;
  location: string;
  village: string;
  taluka: string;
  district: string;
  total_acres: number;
  clusters: number[];
}

interface MukkadamRow {
  mukkadam_id: number;
  mukkadam_name: string;
  mobile_numbers: string;
  manual_status: string | null;
  district: string;
  taluka: string;
  village: string;
  crew_size: number;
  max_crew_capacity: number;
  is_permanent: boolean;
  clusters: { id: number; name: string; mukkadam_type: string }[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
const statusColor: Record<string, string> = {
  active:   "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  on_hold:  "bg-amber-500/15   text-amber-400   border-amber-500/30",
  inactive: "bg-red-500/15     text-red-400     border-red-500/30",
  idle:     "bg-zinc-500/15    text-zinc-400    border-zinc-500/30",
};

// ─── Sub-components ───────────────────────────────────────────────────────────
function SearchBar({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9 pr-4 py-2 bg-card border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
      />
      {value && (
        <button onClick={() => onChange("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

function StatPill({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col items-center px-4 py-2 bg-card border border-border rounded-lg min-w-[80px]">
      <span className="text-lg font-bold text-foreground font-mono">{value}</span>
      <span className="text-[10px] text-muted-foreground uppercase tracking-wide mt-0.5">{label}</span>
    </div>
  );
}

// ─── Farmer Card ─────────────────────────────────────────────────────────────
function FarmerCard({ farmer, onClick }: { farmer: FarmerRow; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="group w-full text-left bg-card border border-border hover:border-emerald-500/50 hover:bg-emerald-500/5 rounded-xl p-4 transition-all duration-200 hover:shadow-lg hover:shadow-emerald-500/5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0 group-hover:bg-emerald-500/20 transition-colors">
            <User className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-sm text-foreground truncate group-hover:text-emerald-400 transition-colors">
              {farmer.farmer_name}
            </p>
            <p className="text-xs text-muted-foreground font-mono mt-0.5">{farmer.farmer_id}</p>
          </div>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all flex-shrink-0 mt-0.5" />
      </div>

      <div className="mt-3 space-y-1.5">
        {farmer.phone_number && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Phone className="h-3 w-3 flex-shrink-0" />
            <span>{farmer.phone_number}</span>
          </div>
        )}
        {(farmer.village || farmer.taluka || farmer.district) && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">
              {[farmer.village, farmer.taluka, farmer.district].filter(Boolean).join(", ")}
            </span>
          </div>
        )}
        {farmer.total_acres > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Layers className="h-3 w-3 flex-shrink-0" />
            <span>{farmer.total_acres.toFixed(2)} acres total</span>
          </div>
        )}
      </div>
    </button>
  );
}

// ─── Mukkadam Card ────────────────────────────────────────────────────────────
function MukkadamCard({ mukkadam, onClick }: { mukkadam: MukkadamRow; onClick: () => void }) {
  const statusKey = mukkadam.manual_status ?? "idle";
  return (
    <button
      onClick={onClick}
      className="group w-full text-left bg-card border border-border hover:border-amber-500/50 hover:bg-amber-500/5 rounded-xl p-4 transition-all duration-200 hover:shadow-lg hover:shadow-amber-500/5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <div className="h-9 w-9 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center flex-shrink-0 group-hover:bg-amber-500/20 transition-colors">
            <Users className="h-4 w-4 text-amber-400" />
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-sm text-foreground truncate group-hover:text-amber-400 transition-colors">
              {mukkadam.mukkadam_name}
            </p>
            <p className="text-xs text-muted-foreground font-mono mt-0.5">#{mukkadam.mukkadam_id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {mukkadam.manual_status && (
            <Badge variant="outline" className={`text-[10px] py-0 h-5 ${statusColor[statusKey] ?? statusColor.idle}`}>
              {mukkadam.manual_status.replace("_", " ")}
            </Badge>
          )}
          <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-amber-400 group-hover:translate-x-0.5 transition-all" />
        </div>
      </div>

      <div className="mt-3 space-y-1.5">
        {mukkadam.mobile_numbers && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Phone className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">{mukkadam.mobile_numbers}</span>
          </div>
        )}
        {(mukkadam.village || mukkadam.taluka || mukkadam.district) && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">
              {[mukkadam.village, mukkadam.taluka, mukkadam.district].filter(Boolean).join(", ")}
            </span>
          </div>
        )}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>
            Crew: <span className="text-foreground font-medium">{mukkadam.crew_size}/{mukkadam.max_crew_capacity}</span>
          </span>
          {mukkadam.is_permanent && (
            <Badge variant="outline" className="text-[10px] py-0 h-5 bg-sky-500/10 text-sky-400 border-sky-500/30">Permanent</Badge>
          )}
        </div>
        {mukkadam.clusters.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {mukkadam.clusters.slice(0, 3).map(c => (
              <span key={c.id} className="text-[10px] bg-muted/40 text-muted-foreground px-1.5 py-0.5 rounded-md">
                {c.name}
              </span>
            ))}
            {mukkadam.clusters.length > 3 && (
              <span className="text-[10px] text-muted-foreground px-1 py-0.5">+{mukkadam.clusters.length - 3}</span>
            )}
          </div>
        )}
      </div>
    </button>
  );
}

// ─── Loading / Error States ───────────────────────────────────────────────────
function Loading({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <Loader2 className="h-6 w-6 animate-spin text-primary" />
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <AlertCircle className="h-8 w-8 text-destructive" />
      <p className="text-sm text-muted-foreground">{message}</p>
      <button onClick={onRetry} className="flex items-center gap-2 text-sm text-primary hover:underline">
        <RefreshCw className="h-3.5 w-3.5" /> Retry
      </button>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-2 text-muted-foreground">
      <Search className="h-8 w-8 opacity-30" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

// ─── Tab types ────────────────────────────────────────────────────────────────
type Tab = "farmers" | "mukkadams";
type View =
  | { type: "directory" }
  | { type: "farmer";   id: string }
  | { type: "mukkadam"; id: number };

// ─── Main Directory Component ─────────────────────────────────────────────────
export default function Directory() {
  const [view, setView] = useState<View>({ type: "directory" });
  const [tab,  setTab]  = useState<Tab>("farmers");

  // Farmers state
  const [farmers,       setFarmers]       = useState<FarmerRow[]>([]);
  const [farmersLoading, setFarmersLoading] = useState(false);
  const [farmersError,   setFarmersError]   = useState<string | null>(null);
  const [farmerSearch,   setFarmerSearch]   = useState("");

  // Mukkadams state
  const [mukkadams,        setMukkadams]        = useState<MukkadamRow[]>([]);
  const [mukkadamsLoading, setMukkadamsLoading] = useState(false);
  const [mukkadamsError,   setMukkadamsError]   = useState<string | null>(null);
  const [mukkadamSearch,   setMukkadamSearch]   = useState("");

  // ── Fetch farmers ─────────────────────────────────────────────────────────
  const fetchFarmers = useCallback(() => {
    setFarmersLoading(true);
    setFarmersError(null);
    fetch(`${API_BASE}/api/farmers/?format=json`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d  => {
        // Handle both paginated ({ results: [] }) and plain array responses
        const list = Array.isArray(d) ? d : (d.results ?? []);
        setFarmers(list);
        setFarmersLoading(false);
      })
      .catch(e => { setFarmersError(e.message); setFarmersLoading(false); });
  }, []);

  // ── Fetch mukkadams ───────────────────────────────────────────────────────
  const fetchMukkadams = useCallback(() => {
    setMukkadamsLoading(true);
    setMukkadamsError(null);
    fetch(`${API_BASE}/api/mukkadams/?format=json`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d  => {
        const list = Array.isArray(d) ? d : (d.results ?? []);
        setMukkadams(list);
        setMukkadamsLoading(false);
      })
      .catch(e => { setMukkadamsError(e.message); setMukkadamsLoading(false); });
  }, []);

  // Load on mount
  useEffect(() => { fetchFarmers();   }, [fetchFarmers]);
  useEffect(() => { fetchMukkadams(); }, [fetchMukkadams]);

  // ── Filtered lists ────────────────────────────────────────────────────────
  const filteredFarmers = farmers.filter(f => {
    const q = farmerSearch.toLowerCase();
    return (
      f.farmer_name?.toLowerCase().includes(q) ||
      f.farmer_id?.toLowerCase().includes(q) ||
      f.phone_number?.includes(q) ||
      f.village?.toLowerCase().includes(q) ||
      f.district?.toLowerCase().includes(q)
    );
  });

  const filteredMukkadams = mukkadams.filter(m => {
    const q = mukkadamSearch.toLowerCase();
    return (
      m.mukkadam_name?.toLowerCase().includes(q) ||
      String(m.mukkadam_id).includes(q) ||
      m.mobile_numbers?.includes(q) ||
      m.village?.toLowerCase().includes(q) ||
      m.district?.toLowerCase().includes(q) ||
      m.clusters?.some(c => c.name.toLowerCase().includes(q))
    );
  });

  // ── Profile views ─────────────────────────────────────────────────────────
  if (view.type === "farmer") {
    return (
      <div>
        {/* Back bar */}
        <div className="sticky top-0 z-50 bg-background/95 backdrop-blur border-b border-border px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setView({ type: "directory" })}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronRight className="h-4 w-4 rotate-180" />
            Back to Directory
          </button>
          <span className="text-muted-foreground/40">•</span>
          <span className="text-sm font-medium text-foreground">Farmer: {view.id}</span>
        </div>
        <FarmerProfile farmerId={view.id} />
      </div>
    );
  }

  if (view.type === "mukkadam") {
    return (
      <div>
        <div className="sticky top-0 z-50 bg-background/95 backdrop-blur border-b border-border px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setView({ type: "directory" })}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronRight className="h-4 w-4 rotate-180" />
            Back to Directory
          </button>
          <span className="text-muted-foreground/40">•</span>
          <span className="text-sm font-medium text-foreground">Mukkadam: #{view.id}</span>
        </div>
        <MukkadamProfile mukkadamId={view.id} />
      </div>
    );
  }

  // ── Directory view ────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-background">
      {/* Page header */}
      <div className="border-b border-border bg-card px-6 py-6">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-2xl font-bold text-foreground tracking-tight">Directory</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Click any card to view the full profile
          </p>

          {/* Stats row */}
          <div className="flex flex-wrap gap-3 mt-4">
            <StatPill label="Farmers"   value={farmers.length}   />
            <StatPill label="Mukkadams" value={mukkadams.length} />
            <StatPill
              label="Total Acres"
              value={farmers.reduce((s, f) => s + (f.total_acres ?? 0), 0).toFixed(1)}
            />
            <StatPill
              label="Total Crew"
              value={mukkadams.reduce((s, m) => s + (m.crew_size ?? 0), 0)}
            />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-border bg-card">
        <div className="max-w-6xl mx-auto px-6 flex gap-0">
          {(["farmers", "mukkadams"] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-6 py-3.5 text-sm font-medium border-b-2 transition-all capitalize flex items-center gap-2 ${
                tab === t
                  ? t === "farmers"
                    ? "border-emerald-500 text-emerald-400"
                    : "border-amber-500 text-amber-400"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "farmers" ? <User className="h-3.5 w-3.5" /> : <Users className="h-3.5 w-3.5" />}
              {t}
              <span className={`text-xs px-1.5 py-0.5 rounded-full font-mono ${
                tab === t
                  ? t === "farmers" ? "bg-emerald-500/15 text-emerald-400" : "bg-amber-500/15 text-amber-400"
                  : "bg-muted text-muted-foreground"
              }`}>
                {t === "farmers" ? filteredFarmers.length : filteredMukkadams.length}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-6 py-6">

        {/* ── FARMERS TAB ── */}
        {tab === "farmers" && (
          <div>
            <div className="flex items-center gap-3 mb-5">
              <div className="flex-1 max-w-sm">
                <SearchBar
                  value={farmerSearch}
                  onChange={setFarmerSearch}
                  placeholder="Search by name, ID, phone, village…"
                />
              </div>
              <button
                onClick={fetchFarmers}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground border border-border rounded-lg px-3 py-2 transition-colors hover:bg-muted/30"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${farmersLoading ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>

            {farmersLoading && <Loading label="Loading farmers…" />}
            {farmersError  && <ErrorState message={farmersError} onRetry={fetchFarmers} />}

            {!farmersLoading && !farmersError && (
              filteredFarmers.length === 0
                ? <EmptyState label={farmerSearch ? `No farmers match "${farmerSearch}"` : "No farmers found"} />
                : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                    {filteredFarmers.map(f => (
                      <FarmerCard
                        key={f.farmer_id}
                        farmer={f}
                        onClick={() => setView({ type: "farmer", id: f.farmer_id })}
                      />
                    ))}
                  </div>
                )
            )}
          </div>
        )}

        {/* ── MUKKADAMS TAB ── */}
        {tab === "mukkadams" && (
          <div>
            <div className="flex items-center gap-3 mb-5">
              <div className="flex-1 max-w-sm">
                <SearchBar
                  value={mukkadamSearch}
                  onChange={setMukkadamSearch}
                  placeholder="Search by name, ID, phone, cluster…"
                />
              </div>
              <button
                onClick={fetchMukkadams}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground border border-border rounded-lg px-3 py-2 transition-colors hover:bg-muted/30"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${mukkadamsLoading ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>

            {mukkadamsLoading && <Loading label="Loading mukkadams…" />}
            {mukkadamsError   && <ErrorState message={mukkadamsError} onRetry={fetchMukkadams} />}

            {!mukkadamsLoading && !mukkadamsError && (
              filteredMukkadams.length === 0
                ? <EmptyState label={mukkadamSearch ? `No mukkadams match "${mukkadamSearch}"` : "No mukkadams found"} />
                : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                    {filteredMukkadams.map(m => (
                      <MukkadamCard
                        key={m.mukkadam_id}
                        mukkadam={m}
                        onClick={() => setView({ type: "mukkadam", id: m.mukkadam_id })}
                      />
                    ))}
                  </div>
                )
            )}
          </div>
        )}

      </div>
    </div>
  );
}