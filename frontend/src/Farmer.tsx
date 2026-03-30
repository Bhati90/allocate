import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { User, Phone, MapPin, Layers, Grape, CreditCard, FileText, BarChart3, Loader2, AlertCircle } from "lucide-react";

const API_BASE = "http://localhost:8002/tender";

// ─── Types ────────────────────────────────────────────────────────────────────
interface Cluster       { id: number; name: string }
// Add to interfaces section
interface PlotActivity {
  id: number;
  activity_name: string;
  scheduled_date: string | null;
  sales_date: string | null;
  total_area: string;
  allocation_status: string;
  is_strict: boolean;
  allocations_summary: {
    mukkadam_name: string;
    allocated_date: string | null;
    work_status: string;
    allocated_area: number;
    allocated_workers: number;
  }[];
}

// Update Plot interface — add activities
interface Plot {
  id: number; name: string; area_acres: string; crop_name: string;
  variety: string; pruning_date: string | null; plot_code: string;
  latitude: string | null; longitude: string | null;
  clusters: Cluster[];
  activities: PlotActivity[];   // ← ADD
}
interface FarmerPayment { payment_id: number; mode: string; amount: string; paid_at: string; paid_status: boolean; notes: string }
interface JobBooking    { booking_id: number; status: string; total_amount: string; advance_paid: string; balance: string; payments: FarmerPayment[] }
interface Job           { job_id: string; crop_name: string; variety: string; status: string; priority: string; booking_amount: string; payment_status: string; scheduled_date: string | null; completed_date: string | null; plot_name: string | null; booking: JobBooking | null; clusters: Cluster[]; is_field_verified: boolean; total_activities_amount: string }
interface FarmerCall    { call_sid: string; purpose: string; status: string; direction: string; duration: number | null; talk_time: number | null; initiated_at: string }
interface JobNote       { id: number; text: string; tags: string[]; tag_labels: string[]; is_resolved: boolean; note_date: string; author: { id: number; username: string; full_name: string } | null; created_at: string }
interface BillLog       { id: number; job_id: string; activity_name: string | null; total_billed: string | null; total_paid: string | null; balance_due: string | null; webhook_booking_status: string | null; webhook_success: boolean | null; sent_at: string }
interface FarmerProfile {
  farmer_id: string; farmer_name: string; phone_number: string;
  location: string; latitude: string | null; longitude: string | null;
  last_synced: string; last_cluster_modified_by_name: string | null;
  clusters: Cluster[]; plots: Plot[]; jobs: Job[];
  calls: FarmerCall[]; notes: JobNote[]; bill_logs: BillLog[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const statusColor: Record<string, string> = {
  pending:        "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  in_progress:    "bg-blue-500/10  text-blue-400  border-blue-500/30",
  completed:      "bg-green-500/10 text-green-400 border-green-500/30",
  cancelled:      "bg-red-500/10   text-red-400   border-red-500/30",
  paid:           "bg-green-500/10 text-green-400 border-green-500/30",
  partial:        "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  PAID:           "bg-green-500/10 text-green-400 border-green-500/30",
  PARTIALLY_PAID: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  UNPAID:         "bg-red-500/10   text-red-400   border-red-500/30",
  answered:       "bg-green-500/10 text-green-400 border-green-500/30",
  failed:         "bg-red-500/10   text-red-400   border-red-500/30",
  scheduled:      "bg-blue-500/10  text-blue-400  border-blue-500/30",
};

const fmt = (v: string | null | undefined) => v ? Number(v).toLocaleString("en-IN") : "—";
const fmtDate = (v: string | null | undefined) => v ? new Date(v).toLocaleDateString("en-IN") : "—";
const fmtDT   = (v: string | null | undefined) => v ? new Date(v).toLocaleString("en-IN")     : "—";

const SBadge = ({ v }: { v: string }) => (
  <Badge variant="outline" className={`text-xs ${statusColor[v] ?? "bg-muted/20 text-muted-foreground border-muted/30"}`}>
    {v.replace(/_/g, " ")}
  </Badge>
);

const Section = ({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) => (
  <Card className="border-border bg-card shadow-sm">
    <CardHeader className="pb-3">
      <CardTitle className="flex items-center gap-2 text-base text-card-foreground">
        <Icon className="h-4 w-4 text-primary" />
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
);

const Field = ({ label, value }: { label: string; value: React.ReactNode }) => (
  <div className="space-y-1">
    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{label}</p>
    <div className="text-sm text-card-foreground font-medium">{value ?? <span className="text-muted-foreground italic">—</span>}</div>
  </div>
);

// ─── Component ────────────────────────────────────────────────────────────────
interface Props { farmerId: string }

const FarmerProfile = ({ farmerId }: Props) => {
  const [data,    setData]    = useState<FarmerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/farmers/${farmerId}/profile/`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d  => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [farmerId]);

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <span className="ml-3 text-muted-foreground">Loading farmer profile…</span>
    </div>
  );

  if (error || !data) return (
    <div className="flex items-center justify-center min-h-screen gap-3 text-destructive">
      <AlertCircle className="h-6 w-6" />
      <span>{error ?? "Failed to load profile"}</span>
    </div>
  );

  const f = data;

  // Aggregate booking summary across all jobs
  const allPayments = f.jobs.flatMap(j => j.booking?.payments ?? []);
  const totalBilled = f.jobs.reduce((s, j) => s + Number(j.booking?.total_amount ?? 0), 0);
  const totalPaid   = f.jobs.reduce((s, j) => s + Number(j.booking?.advance_paid ?? 0), 0);
  const totalBal    = f.jobs.reduce((s, j) => s + Number(j.booking?.balance ?? 0), 0);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-primary px-6 py-8">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 rounded-full bg-primary-foreground/20 flex items-center justify-center">
              <User className="h-8 w-8 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-primary-foreground">{f.farmer_name}</h1>
              <p className="text-primary-foreground/70 text-sm">Farmer ID: {f.farmer_id}</p>
              <div className="flex flex-wrap gap-2 mt-2">
                {f.clusters.map(c => (
                  <Badge key={c.id} variant="secondary" className="bg-primary-foreground/20 text-primary-foreground border-0 text-xs">
                    {c.name}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">

        {/* Basic Info + Location */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Section icon={User} title="Basic Information">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Farmer ID"   value={f.farmer_id} />
              <Field label="Name"        value={f.farmer_name} />
              <Field label="Phone"       value={f.phone_number} />
              <Field label="Last Synced" value={fmtDate(f.last_synced)} />
              <Field label="Clusters"    value={f.clusters.map(c => c.name).join(", ")} />
              <Field label="Modified By" value={f.last_cluster_modified_by_name} />
            </div>
          </Section>

          <Section icon={MapPin} title="Location">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Location"  value={f.location} />
              <Field label="Latitude"  value={f.latitude} />
              <Field label="Longitude" value={f.longitude} />
            </div>
            {f.latitude && f.longitude && (
              <div className="mt-4 h-32 bg-muted rounded-lg flex items-center justify-center">
                <span className="text-muted-foreground text-sm">📍 ({f.latitude}, {f.longitude})</span>
              </div>
            )}
          </Section>
        </div>

        {/* Plots */}
        <Section icon={Layers} title={`Plots (${f.plots.length})`}>
          {f.plots.length === 0 ? <p className="text-muted-foreground text-sm">No plots found.</p> : (
            <div className="space-y-4">
              {f.plots.map(plot => (
                <div key={plot.id} className="border border-border rounded-lg p-4 bg-secondary/30">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-semibold text-card-foreground">{plot.name}</h4>
                    {plot.plot_code && <Badge variant="outline" className="text-xs">{plot.plot_code}</Badge>}
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Field label="Area (ac)"    value={`${plot.area_acres} ac`} />
                    <Field label="Crop"         value={plot.crop_name}  />
                    <Field label="Variety"      value={plot.variety}    />
                    <Field label="Pruning Date" value={fmtDate(plot.pruning_date)} />
                    <Field label="Clusters"     value={plot.clusters.map(c => c.name).join(", ")} />
                    <Field label="Latitude"     value={plot.latitude}   />
                    <Field label="Longitude"    value={plot.longitude}  />
                  </div>
                  {plot.activities.length > 0 && (
  <div className="mt-4">
    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
      Activities
    </p>
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            {["Activity","Date","Area","Status","Mukkadam","Work Status"].map(h => (
              <th key={h} className="text-left py-1 px-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {plot.activities.map(act => (
            <tr key={act.id} className="border-b border-border/40 hover:bg-muted/20">
              <td className="py-1 px-2 font-medium">
                {act.activity_name}
                {act.is_strict && <span className="ml-1 text-orange-400 text-[10px]">strict</span>}
              </td>
              <td className="py-1 px-2">{fmtDate(act.scheduled_date)}</td>
              <td className="py-1 px-2">{act.total_area} ac</td>
              <td className="py-1 px-2"><SBadge v={act.allocation_status} /></td>
              <td className="py-1 px-2">
                {act.allocations_summary.length === 0
                  ? <span className="text-muted-foreground italic">Unallocated</span>
                  : act.allocations_summary.map((a, i) => (
                    <div key={i}>{a.mukkadam_name}</div>
                  ))
                }
              </td>
              <td className="py-1 px-2">
                {act.allocations_summary.length === 0
                  ? '—'
                  : act.allocations_summary.map((a, i) => (
                    <div key={i}><SBadge v={a.work_status} /></div>
                  ))
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
)}
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Jobs */}
        <Section icon={Grape} title={`Jobs (${f.jobs.length})`}>
          {f.jobs.length === 0 ? <p className="text-muted-foreground text-sm">No jobs found.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-muted-foreground text-xs">
                    {["Job ID","Plot","Crop","Status","Priority","Booking ₹","Payment","Scheduled"].map(h => (
                      <th key={h} className="text-left py-2 px-1 font-medium whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {f.jobs.map(job => (
                    <tr key={job.job_id} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-2 px-1 font-mono text-xs">{job.job_id}</td>
                      <td className="py-2 px-1">{job.plot_name ?? "—"}</td>
                      <td className="py-2 px-1">{job.crop_name || "—"}</td>
                      <td className="py-2 px-1"><SBadge v={job.status} /></td>
                      <td className="py-2 px-1"><Badge variant="outline" className="text-xs">{job.priority}</Badge></td>
                      <td className="py-2 px-1 text-right font-medium">₹{fmt(job.booking_amount)}</td>
                      <td className="py-2 px-1"><SBadge v={job.payment_status} /></td>
                      <td className="py-2 px-1 whitespace-nowrap">{fmtDate(job.scheduled_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        {/* Booking Summary + Payments */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Section icon={CreditCard} title="Booking Summary">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Total Jobs"   value={f.jobs.length} />
              <Field label="Total Billed" value={`₹${totalBilled.toLocaleString("en-IN")}`} />
              <Field label="Total Paid"   value={`₹${totalPaid.toLocaleString("en-IN")}`} />
              <Field label="Balance Due"  value={<span className="text-orange-400 font-bold">₹{totalBal.toLocaleString("en-IN")}</span>} />
            </div>
          </Section>

          <Section icon={CreditCard} title={`Payment History (${allPayments.length})`}>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {allPayments.length === 0
                ? <p className="text-muted-foreground text-sm">No payments yet.</p>
                : allPayments.map(p => (
                  <div key={p.payment_id} className="flex items-center justify-between border-b border-border/50 pb-2">
                    <div>
                      <p className="text-sm font-medium">₹{fmt(p.amount)}</p>
                      <p className="text-xs text-muted-foreground">{p.mode} • {fmtDate(p.paid_at)}</p>
                    </div>
                    <Badge variant="outline" className="text-xs bg-green-500/10 text-green-400 border-green-500/30">Paid</Badge>
                  </div>
                ))
              }
            </div>
          </Section>
        </div>

        {/* Calls + Notes */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Section icon={Phone} title={`Call History (${f.calls.length})`}>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {f.calls.length === 0
                ? <p className="text-muted-foreground text-sm">No calls recorded.</p>
                : f.calls.map(c => (
                  <div key={c.call_sid} className="flex items-center justify-between border-b border-border/50 pb-2">
                    <div>
                      <p className="text-sm font-medium capitalize">{c.purpose.replace(/_/g, " ")}</p>
                      <p className="text-xs text-muted-foreground">{fmtDT(c.initiated_at)} • {c.duration ?? 0}s</p>
                    </div>
                    <SBadge v={c.status} />
                  </div>
                ))
              }
            </div>
          </Section>

          <Section icon={FileText} title={`Notes (${f.notes.length})`}>
            <div className="space-y-3 max-h-60 overflow-y-auto">
              {f.notes.length === 0
                ? <p className="text-muted-foreground text-sm">No notes yet.</p>
                : f.notes.map(n => (
                  <div key={n.id} className="border border-border rounded-lg p-3 bg-secondary/20">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      {n.tag_labels.map(t => <Badge key={t} variant="outline" className="text-xs">{t}</Badge>)}
                      {!n.is_resolved && <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30 text-xs">Unresolved</Badge>}
                    </div>
                    <p className="text-sm">{n.text}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      By {n.author?.full_name ?? "Unknown"} • {fmtDate(n.note_date)}
                    </p>
                  </div>
                ))
              }
            </div>
          </Section>
        </div>

        {/* Bill Webhook Logs */}
        <Section icon={BarChart3} title={`Bill Webhook Logs (${f.bill_logs.length})`}>
          {f.bill_logs.length === 0 ? <p className="text-muted-foreground text-sm">No webhook logs.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-muted-foreground text-xs">
                    {["Job ID","Activity","Billed","Paid","Balance","Status","Sent At"].map(h => (
                      <th key={h} className="text-left py-2 px-1 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {f.bill_logs.map(l => (
                    <tr key={l.id} className="border-b border-border/50">
                      <td className="py-2 px-1 font-mono text-xs">{l.job_id}</td>
                      <td className="py-2 px-1">{l.activity_name ?? "—"}</td>
                      <td className="py-2 px-1">₹{fmt(l.total_billed)}</td>
                      <td className="py-2 px-1">₹{fmt(l.total_paid)}</td>
                      <td className="py-2 px-1 text-orange-400 font-semibold">₹{fmt(l.balance_due)}</td>
                      <td className="py-2 px-1">{l.webhook_booking_status ?? "—"}</td>
                      <td className="py-2 px-1 whitespace-nowrap">{fmtDT(l.sent_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

      </div>
    </div>
  );
};

export default FarmerProfile;