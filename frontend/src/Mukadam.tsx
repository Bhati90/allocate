import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Users, User, MapPin, Activity, CreditCard, Calendar, Clock, Shield, Loader2, AlertCircle } from "lucide-react";

const API_BASE = "http://localhost:8002/tender";

// ─── Types ────────────────────────────────────────────────────────────────────
interface ClusterAssignment {
  cluster_name: string; mukkadam_type: string; weekly_amount: string;
  transport_price: string; advance_amount: string; advance_is_manual: boolean;
  weekly_payment_day: string; is_active: boolean; joined_date: string | null;
  updown_mode: string | null; updown_from_date: string | null; updown_to_date: string | null;
}
interface ActivityRate {
  rate_id: number; activity_id: number; activity_name: string;
  rate_per_acre: string; productivity_per_worker: string; is_active: boolean;
}
interface Availability {
  id: number; date: string; available_crew_size: number; is_available: boolean;
  is_on_leave: boolean; allocated_workers: number; remaining_capacity: number; is_manually_set: boolean;
}
interface MAllocation {
  id: number; job_id: string; activity_name: string; farmer_name: string;
  cluster_name: string | null; allocated_date: string; allocated_area: string;
  allocated_workers: number; farmer_rate: string; mukkadam_rate: string;
  farmer_amount: string; mukkadam_amount: string;
  status: string; work_status: string; payment_status: string;
  allows_second_job: boolean; is_auto_allocated: boolean; is_carry_forward: boolean;
  actual_area_done: string | null; actual_crew_size: number | null;
  report_submitted: boolean; farmer_agreed: boolean;
}
interface MPayment {
  payment_id: string; mode: string; amount: string; notes: string; paid_at: string;
}
interface WeeklyPayment { id: number; cluster_name: string | null; week_start: string; amount: string; status: string; paid_at: string | null }
interface Leave    { id: number; date: string; leave_type: string; crew_on_leave: number; reason: string; is_active: boolean }
interface ExtraWorker { id: number; date: string; workers: number; note: string }
interface OTPReq   { id: number; phone: string; crew_size: number | null; otp_type: string; requested_at: string; is_used: boolean }

interface MukkadamProfile {
  mukkadam_id: number; mukkadam_name: string; mobile_numbers: string;
  manual_status: string | null; manual_status_note: string | null;
  manual_status_set_by: string | null; manual_status_set_at: string | null;
  is_permanent: boolean;
  state: string; district: string; taluka: string; village: string;
  current_latitude: string | null; current_longitude: string | null;
  crew_size: number; max_crew_capacity: number;
  has_smartphone: string; work_mode: string;
  start_date: string | null; end_date: string | null;
  efficiency: string;
  tender_activities: Record<string, boolean>;
  rate_card: Record<string, number>;
  cluster_assignments: ClusterAssignment[];
  activity_rates: ActivityRate[];
  daily_availability: Availability[];
  allocations: MAllocation[];
  payments: MPayment[];
  weekly_payments: WeeklyPayment[];
  leaves: Leave[];
  extra_workers: ExtraWorker[];
  otp_requests: OTPReq[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const statusColor: Record<string, string> = {
  active:           "bg-green-500/10 text-green-400 border-green-500/30",
  on_hold:          "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  inactive:         "bg-red-500/10   text-red-400   border-red-500/30",
  scheduled:        "bg-blue-500/10  text-blue-400  border-blue-500/30",
  completed:        "bg-green-500/10 text-green-400 border-green-500/30",
  in_progress:      "bg-blue-500/10  text-blue-400  border-blue-500/30",
  cancelled:        "bg-red-500/10   text-red-400   border-red-500/30",
  paid:             "bg-green-500/10 text-green-400 border-green-500/30",
  pending:          "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  done:             "bg-green-500/10 text-green-400 border-green-500/30",
  work_not_started: "bg-muted/30 text-muted-foreground border-muted/30",
  dispute:          "bg-orange-500/10 text-orange-400 border-orange-500/30",
  settled:          "bg-purple-500/10 text-purple-400 border-purple-500/30",
};

const fmt     = (v: string | null | undefined) => v ? Number(v).toLocaleString("en-IN") : "—";
const fmtDate = (v: string | null | undefined) => v ? new Date(v).toLocaleDateString("en-IN")  : "—";
const fmtDT   = (v: string | null | undefined) => v ? new Date(v).toLocaleString("en-IN")      : "—";

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
interface Props { mukkadamId: number | string }

const MukkadamProfile = ({ mukkadamId }: Props) => {
  const [data,    setData]    = useState<MukkadamProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/mukkadams/${mukkadamId}/profile/`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d  => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [mukkadamId]);

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <span className="ml-3 text-muted-foreground">Loading mukkadam profile…</span>
    </div>
  );

  if (error || !data) return (
    <div className="flex items-center justify-center min-h-screen gap-3 text-destructive">
      <AlertCircle className="h-6 w-6" />
      <span>{error ?? "Failed to load profile"}</span>
    </div>
  );

  const m = data;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-primary px-6 py-8">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 rounded-full bg-primary-foreground/20 flex items-center justify-center">
              <Users className="h-8 w-8 text-primary-foreground" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-bold text-primary-foreground">{m.mukkadam_name}</h1>
                {m.manual_status && <SBadge v={m.manual_status} />}
              </div>
              <p className="text-primary-foreground/70 text-sm">Mukkadam ID: {m.mukkadam_id}</p>
              <div className="flex flex-wrap gap-2 mt-2">
                {m.is_permanent && <Badge className="bg-primary-foreground/20 text-primary-foreground border-0 text-xs">Permanent</Badge>}
                <Badge className="bg-primary-foreground/20 text-primary-foreground border-0 text-xs">Crew: {m.crew_size}/{m.max_crew_capacity}</Badge>
                <Badge className="bg-primary-foreground/20 text-primary-foreground border-0 text-xs">
                  📱 {m.has_smartphone === "yes" ? "Smartphone" : "No Smartphone"}
                </Badge>
                {m.work_mode && <Badge className="bg-primary-foreground/20 text-primary-foreground border-0 text-xs">{m.work_mode}</Badge>}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">

        {/* Basic + Location */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Section icon={User} title="Basic Information">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Mukkadam ID"    value={m.mukkadam_id.toString()} />
              <Field label="Name"           value={m.mukkadam_name} />
              <Field label="Mobile"         value={m.mobile_numbers} />
              <Field label="Work Mode"      value={m.work_mode} />
              <Field label="Crew Size"      value={m.crew_size} />
              <Field label="Max Capacity"   value={m.max_crew_capacity} />
              <Field label="Smartphone"     value={m.has_smartphone} />
              <Field label="Permanent"      value={m.is_permanent ? "Yes" : "No"} />
              <Field label="Efficiency"     value={`${m.efficiency} ac/worker/day`} />
              <Field label="Status Note"    value={m.manual_status_note} />
              <Field label="Status Set By"  value={m.manual_status_set_by} />
              <Field label="Status Set At"  value={fmtDate(m.manual_status_set_at)} />
            </div>
          </Section>

          <Section icon={MapPin} title="Location & Dates">
            <div className="grid grid-cols-2 gap-4">
              <Field label="State"     value={m.state}    />
              <Field label="District"  value={m.district} />
              <Field label="Taluka"    value={m.taluka}   />
              <Field label="Village"   value={m.village}  />
              <Field label="Latitude"  value={m.current_latitude}  />
              <Field label="Longitude" value={m.current_longitude} />
              <Field label="Start Date" value={fmtDate(m.start_date)} />
              <Field label="End Date"   value={fmtDate(m.end_date)}   />
            </div>
          </Section>
        </div>

        {/* Cluster Assignments */}
        <Section icon={Shield} title={`Cluster Assignments (${m.cluster_assignments.length})`}>
          {m.cluster_assignments.length === 0
            ? <p className="text-muted-foreground text-sm">No cluster assignments.</p>
            : (
              <div className="space-y-4">
                {m.cluster_assignments.map((ca, i) => (
                  <div key={i} className="border border-border rounded-lg p-4 bg-secondary/30">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-semibold">{ca.cluster_name}</h4>
                      <div className="flex gap-2">
                        <Badge variant="outline" className="text-xs">{ca.mukkadam_type}</Badge>
                        {ca.is_active
                          ? <Badge className="bg-green-500/10 text-green-400 border-green-500/30 text-xs">Active</Badge>
                          : <Badge className="bg-red-500/10 text-red-400 border-red-500/30 text-xs">Inactive</Badge>
                        }
                      </div>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <Field label="Weekly Amount"    value={`₹${fmt(ca.weekly_amount)}`} />
                      <Field label="Transport Price"  value={`₹${fmt(ca.transport_price)}`} />
                      <Field label="Advance Amount"   value={`₹${fmt(ca.advance_amount)}`} />
                      <Field label="Advance Manual"   value={ca.advance_is_manual ? "Yes" : "No"} />
                      <Field label="Payment Day"      value={ca.weekly_payment_day} />
                      <Field label="Joined"           value={fmtDate(ca.joined_date)} />
                      {ca.mukkadam_type === "updown" && <>
                        <Field label="Updown Mode"  value={ca.updown_mode} />
                        <Field label="Updown From"  value={fmtDate(ca.updown_from_date)} />
                        <Field label="Updown To"    value={fmtDate(ca.updown_to_date)} />
                      </>}
                    </div>
                  </div>
                ))}
              </div>
            )
          }
        </Section>

        {/* Activity Rates */}
        <Section icon={Activity} title={`Activity Rates (${m.activity_rates.length})`}>
          {m.activity_rates.length === 0
            ? <p className="text-muted-foreground text-sm">No activity rates configured.</p>
            : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground text-xs">
                      {["Activity","Rate/Acre","Productivity/Worker","Status"].map(h => (
                        <th key={h} className="text-left py-2 px-1 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {m.activity_rates.map(r => (
                      <tr key={r.rate_id} className="border-b border-border/50">
                        <td className="py-2 px-1 font-medium">{r.activity_name}</td>
                        <td className="py-2 px-1">₹{fmt(r.rate_per_acre)}</td>
                        <td className="py-2 px-1">{r.productivity_per_worker} ac/worker</td>
                        <td className="py-2 px-1">
                          {r.is_active
                            ? <Badge className="bg-green-500/10 text-green-400 border-green-500/30 text-xs">Active</Badge>
                            : <Badge className="bg-muted/20 text-muted-foreground border-muted/30 text-xs">Inactive</Badge>
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </Section>

        {/* Availability */}
        <Section icon={Calendar} title={`Availability (${m.daily_availability.length} days)`}>
          {m.daily_availability.length === 0
            ? <p className="text-muted-foreground text-sm">No availability data.</p>
            : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground text-xs">
                      {["Date","Crew Size","Allocated","Remaining","Available","On Leave","Manual"].map(h => (
                        <th key={h} className="text-left py-2 px-1 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {m.daily_availability.map(av => (
                      <tr key={av.id} className="border-b border-border/50">
                        <td className="py-2 px-1 font-mono text-xs whitespace-nowrap">{av.date}</td>
                        <td className="py-2 px-1 text-center">{av.available_crew_size}</td>
                        <td className="py-2 px-1 text-center">{av.allocated_workers}</td>
                        <td className="py-2 px-1 text-center">{av.remaining_capacity}</td>
                        <td className="py-2 px-1">{av.is_available ? "✅" : "❌"}</td>
                        <td className="py-2 px-1">{av.is_on_leave  ? "🏖️ Yes" : "No"}</td>
                        <td className="py-2 px-1">{av.is_manually_set ? "✏️ Yes" : "Auto"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </Section>

        {/* Allocations */}
        <Section icon={Activity} title={`Allocations — Last 30 Days (${m.allocations.length})`}>
          {m.allocations.length === 0
            ? <p className="text-muted-foreground text-sm">No allocations in last 30 days.</p>
            : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground text-xs">
                      {["Job ID","Activity","Farmer","Date","Area","Workers","F.Rate","M.Rate","Status","Work","Payment","Flags"].map(h => (
                        <th key={h} className="text-left py-2 px-1 font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {m.allocations.map(a => (
                      <tr key={a.id} className="border-b border-border/50 hover:bg-muted/20">
                        <td className="py-2 px-1 font-mono text-xs">{a.job_id}</td>
                        <td className="py-2 px-1">{a.activity_name}</td>
                        <td className="py-2 px-1">{a.farmer_name}</td>
                        <td className="py-2 px-1 whitespace-nowrap">{a.allocated_date}</td>
                        <td className="py-2 px-1">{a.allocated_area} ac</td>
                        <td className="py-2 px-1 text-center">{a.allocated_workers}</td>
                        <td className="py-2 px-1">₹{fmt(a.farmer_rate)}</td>
                        <td className="py-2 px-1">₹{fmt(a.mukkadam_rate)}</td>
                        <td className="py-2 px-1"><SBadge v={a.status} /></td>
                        <td className="py-2 px-1"><SBadge v={a.work_status} /></td>
                        <td className="py-2 px-1"><SBadge v={a.payment_status} /></td>
                        <td className="py-2 px-1 text-center text-xs whitespace-nowrap">
                          {a.allows_second_job  && "🔄"}
                          {a.is_auto_allocated  && "🤖"}
                          {a.is_carry_forward   && "➡️"}
                          {a.report_submitted   && "📋"}
                          {a.farmer_agreed      && "✅"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </Section>

        {/* Payments + Weekly Payments */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Section icon={CreditCard} title={`Payments (${m.payments.length})`}>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {m.payments.length === 0
                ? <p className="text-muted-foreground text-sm">No payments.</p>
                : m.payments.map((p, i) => (
                  <div key={i} className="flex items-center justify-between border-b border-border/50 pb-2">
                    <div>
                      <p className="text-sm font-medium">₹{fmt(p.amount)}</p>
                      <p className="text-xs text-muted-foreground">{p.mode} • {fmtDate(p.paid_at)}</p>
                      {p.notes && <p className="text-xs text-muted-foreground">{p.notes}</p>}
                    </div>
                    <span className="text-xs font-mono text-muted-foreground">{p.payment_id}</span>
                  </div>
                ))
              }
            </div>
          </Section>

          <Section icon={CreditCard} title={`Weekly Payments (${m.weekly_payments.length})`}>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {m.weekly_payments.length === 0
                ? <p className="text-muted-foreground text-sm">No weekly payments.</p>
                : m.weekly_payments.map(wp => (
                  <div key={wp.id} className="flex items-center justify-between border-b border-border/50 pb-2">
                    <div>
                      <p className="text-sm font-medium">₹{fmt(wp.amount)}</p>
                      <p className="text-xs text-muted-foreground">{wp.cluster_name ?? "—"} • Week of {wp.week_start}</p>
                    </div>
                    <SBadge v={wp.status} />
                  </div>
                ))
              }
            </div>
          </Section>
        </div>

        {/* Leaves + Extra Workers + OTP */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Section icon={Calendar} title={`Leaves (${m.leaves.length})`}>
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {m.leaves.length === 0
                ? <p className="text-muted-foreground text-sm">No leaves.</p>
                : m.leaves.map(l => (
                  <div key={l.id} className="border border-border rounded-lg p-3 bg-red-500/5">
                    <p className="text-sm font-medium">{l.date} — {l.reason}</p>
                    <p className="text-xs text-muted-foreground">
                      {l.leave_type} • Crew on leave: {l.crew_on_leave} • {l.is_active ? "Active" : "Cancelled"}
                    </p>
                  </div>
                ))
              }
            </div>
          </Section>

          <Section icon={Users} title={`Extra Workers (${m.extra_workers.length})`}>
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {m.extra_workers.length === 0
                ? <p className="text-muted-foreground text-sm">No extra worker logs.</p>
                : m.extra_workers.map(ew => (
                  <div key={ew.id} className="border border-border rounded-lg p-3 bg-blue-500/5">
                    <p className="text-sm font-medium">{ew.date} — +{ew.workers} workers</p>
                    <p className="text-xs text-muted-foreground">{ew.note}</p>
                  </div>
                ))
              }
            </div>
          </Section>

          <Section icon={Clock} title={`OTP Requests (${m.otp_requests.length})`}>
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {m.otp_requests.length === 0
                ? <p className="text-muted-foreground text-sm">No OTP requests.</p>
                : m.otp_requests.map(otp => (
                  <div key={otp.id} className="border border-border rounded-lg p-3">
                    <p className="text-sm font-medium capitalize">{otp.otp_type} Work</p>
                    <p className="text-xs text-muted-foreground">📱 {otp.phone} • Crew: {otp.crew_size ?? "—"}</p>
                    <p className="text-xs text-muted-foreground">
                      {fmtDT(otp.requested_at)} • {otp.is_used ? "✅ Used" : "⏳ Pending"}
                    </p>
                  </div>
                ))
              }
            </div>
          </Section>
        </div>

      </div>
    </div>
  );
};

export default MukkadamProfile;