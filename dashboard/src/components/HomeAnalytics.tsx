"use client";

import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

interface StateRiskDatum {
  stateSlug: string;
  displayState: string;
  mpCount: number;
  avgScore: number;
  corruptionIndex: number;
  avgCriminalRisk: number;
  avgAttendanceRisk: number;
  totalCases: number;
  seriousCases: number;
  pendingCases: number;
  mpsWithCases: number;
}

interface PartyRiskDatum {
  party: string;
  mpCount: number;
  avgScore: number;
  corruptionIndex: number;
  avgCriminalRisk: number;
  avgAttendanceRisk: number;
  avgParticipationRisk: number;
  avgCommitteeRisk: number;
  totalCases: number;
  seriousCases: number;
  mpsWithCases: number;
  caseRate: number;
}

interface CriminalLeaderDatum {
  mpName: string;
  party: string;
  constituency: string;
  state: string;
  href: string;
  totalCases: number;
  seriousCases: number;
  pendingCases: number;
  risk: number;
}

interface HomeAnalyticsProps {
  data: {
    stateRisk: StateRiskDatum[];
    stateCriminalCases: StateRiskDatum[];
    partyStats: PartyRiskDatum[];
    criminalCaseLeaders: CriminalLeaderDatum[];
  };
}

const HEAT_COLORS = ["#22C55E", "#A3E635", "#FACC15", "#FB923C", "#EF4444", "#BE123C"];
const PARTY_COLORS = ["#FF6B00", "#2563EB", "#10B981", "#EF4444", "#8B5CF6", "#F59E0B", "#06B6D4", "#EC4899"];

function shortLabel(value: string, max = 15) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function heatColor(value: number) {
  const index = Math.min(HEAT_COLORS.length - 1, Math.max(0, Math.floor(value / 18)));
  return HEAT_COLORS[index];
}

function riskLabel(value: number) {
  if (value >= 70) return "Critical";
  if (value >= 55) return "High";
  if (value >= 40) return "Watch";
  return "Lower";
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const item = payload[0]?.payload ?? {};
  return (
    <div className="max-w-xs border-3 border-white bg-[#150f23] p-3 font-mono text-xs text-white shadow-[5px_5px_0_0_#c2ef4e]">
      <div className="mb-2 font-sans text-sm font-black uppercase text-[#c2ef4e]">
        {item.displayState || item.party || label}
      </div>
      {payload.map((entry: any) => (
        <div key={entry.name} className="flex justify-between gap-5">
          <span className="text-white/70">{entry.name}</span>
          <span className="font-black" style={{ color: entry.color }}>
            {entry.value}
          </span>
        </div>
      ))}
      {item.mpCount ? <div className="mt-1 text-white/60">MPs: {item.mpCount}</div> : null}
    </div>
  );
}

function AnalyticsCard({
  title,
  kicker,
  children,
  className = "",
}: {
  title: string;
  kicker: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`border-3 border-[#584674] bg-white/10 p-4 shadow-[6px_6px_0_0_rgba(194,239,78,0.35)] backdrop-blur ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] font-black uppercase tracking-[0.2em] text-[#c2ef4e]">{kicker}</p>
          <h3 className="mt-1 text-xl font-black uppercase leading-tight text-white">{title}</h3>
        </div>
      </div>
      {children}
    </section>
  );
}

export function HomeAnalytics({ data }: HomeAnalyticsProps) {
  const partyHeat = data.partyStats.slice(0, 8);
  const worstState = data.stateRisk[0];
  const criminalTotal = data.stateCriminalCases.reduce((sum, state) => sum + state.totalCases, 0);
  const seriousTotal = data.stateCriminalCases.reduce((sum, state) => sum + state.seriousCases, 0);

  return (
    <section className="relative overflow-hidden border-5 border-ink bg-[#1f1633] p-4 text-white shadow-brutal-lg md:p-6">
      <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-danger/30 blur-3xl" />
      <div className="absolute -bottom-24 left-10 h-72 w-72 rounded-full bg-[#c2ef4e]/20 blur-3xl" />
      <div className="relative">
        <div className="mb-6 grid gap-4 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
          <div>
            <div className="inline-flex border-3 border-[#c2ef4e] bg-[#150f23] px-3 py-1 font-mono text-xs font-black uppercase tracking-[0.18em] text-[#c2ef4e] shadow-[3px_3px_0_0_#79628c]">
              National risk command center
            </div>
            <h2 className="mt-4 max-w-4xl text-3xl font-black uppercase leading-none tracking-tight md:text-5xl">
              State, party and criminal-case dashboards
            </h2>
            <p className="mt-3 max-w-3xl text-sm font-medium leading-6 text-white/70 md:text-base">
              A high-contrast risk layer built from composite score weakness, criminal-record scores,
              attendance, participation and committee signals. Labels use “risk” / “red flag” language
              so the site stays evidence-led instead of making unsupported corruption claims.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="border-3 border-white bg-danger p-3 text-center shadow-[4px_4px_0_0_#150f23]">
              <div className="font-mono text-2xl font-black">{worstState?.corruptionIndex ?? 0}</div>
              <div className="text-[10px] font-black uppercase">Top state index</div>
            </div>
            <div className="border-3 border-white bg-[#c2ef4e] p-3 text-center text-[#150f23] shadow-[4px_4px_0_0_#150f23]">
              <div className="font-mono text-2xl font-black">{criminalTotal}</div>
              <div className="text-[10px] font-black uppercase">Cases in top states</div>
            </div>
            <div className="border-3 border-white bg-[#79628c] p-3 text-center shadow-[4px_4px_0_0_#150f23]">
              <div className="font-mono text-2xl font-black">{seriousTotal}</div>
              <div className="text-[10px] font-black uppercase">Serious cases</div>
            </div>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-2">
          <AnalyticsCard title="State-wise corruption risk index" kicker="Worst average risk by state">
            <div className="h-[420px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.stateRisk}
                  layout="vertical"
                  margin={{ top: 8, right: 18, bottom: 8, left: 70 }}
                >
                  <CartesianGrid stroke="#362d59" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: "#e5e7eb", fontSize: 11, fontFamily: "JetBrains Mono" }} />
                  <YAxis
                    dataKey="displayState"
                    type="category"
                    width={104}
                    tick={{ fill: "#ffffff", fontSize: 11, fontWeight: 700 }}
                    tickFormatter={(value) => shortLabel(value, 14)}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.08)" }} />
                  <Bar dataKey="corruptionIndex" name="Risk index" radius={[0, 8, 8, 0]}>
                    {data.stateRisk.map((entry) => (
                      <Cell key={entry.stateSlug} fill={heatColor(entry.corruptionIndex)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </AnalyticsCard>

          <AnalyticsCard title="Most criminal cases by state" kicker="Total and serious case load">
            <div className="h-[420px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.stateCriminalCases}
                  layout="vertical"
                  margin={{ top: 8, right: 18, bottom: 8, left: 70 }}
                >
                  <CartesianGrid stroke="#362d59" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tick={{ fill: "#e5e7eb", fontSize: 11, fontFamily: "JetBrains Mono" }} />
                  <YAxis
                    dataKey="displayState"
                    type="category"
                    width={104}
                    tick={{ fill: "#ffffff", fontSize: 11, fontWeight: 700 }}
                    tickFormatter={(value) => shortLabel(value, 14)}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.08)" }} />
                  <Bar dataKey="totalCases" name="Total cases" fill="#FB923C" radius={[0, 8, 8, 0]} />
                  <Bar dataKey="seriousCases" name="Serious cases" fill="#EF4444" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </AnalyticsCard>

          <AnalyticsCard title="Party risk matrix" kicker="Bubble = party strength">
            <div className="h-[360px]">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 26, bottom: 28, left: 8 }}>
                  <CartesianGrid stroke="#362d59" strokeDasharray="3 3" />
                  <XAxis
                    type="number"
                    dataKey="corruptionIndex"
                    name="Risk index"
                    domain={[0, 100]}
                    label={{ value: "Risk index →", position: "insideBottom", offset: -12, fill: "#e5e7eb", fontSize: 11 }}
                    tick={{ fill: "#e5e7eb", fontSize: 11, fontFamily: "JetBrains Mono" }}
                  />
                  <YAxis
                    type="number"
                    dataKey="avgCriminalRisk"
                    name="Criminal risk"
                    domain={[0, 100]}
                    label={{ value: "Criminal risk →", angle: -90, position: "insideLeft", fill: "#e5e7eb", fontSize: 11 }}
                    tick={{ fill: "#e5e7eb", fontSize: 11, fontFamily: "JetBrains Mono" }}
                  />
                  <ZAxis dataKey="mpCount" range={[90, 900]} name="MPs" />
                  <Tooltip content={<ChartTooltip />} cursor={{ strokeDasharray: "3 3", stroke: "#c2ef4e" }} />
                  <Scatter data={data.partyStats} name="Parties">
                    {data.partyStats.map((entry, index) => (
                      <Cell key={entry.party} fill={PARTY_COLORS[index % PARTY_COLORS.length]} stroke="#fff" strokeWidth={2} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {data.partyStats.slice(0, 7).map((party, index) => (
                <span key={party.party} className="border border-white/40 px-2 py-1 font-mono text-[10px] font-bold uppercase text-white/80">
                  <span className="mr-1 inline-block h-2 w-2" style={{ backgroundColor: PARTY_COLORS[index % PARTY_COLORS.length] }} />
                  {shortLabel(party.party, 18)} · {party.mpCount}
                </span>
              ))}
            </div>
          </AnalyticsCard>

          <AnalyticsCard title="Party risk heatmap" kicker="Where each party is weakest">
            <div className="space-y-2">
              <div className="grid grid-cols-[1.2fr_repeat(5,0.65fr)] gap-1 font-mono text-[10px] font-black uppercase text-white/55">
                <div>Party</div>
                <div>Index</div>
                <div>Crim</div>
                <div>Attend</div>
                <div>Partic.</div>
                <div>Cases</div>
              </div>
              {partyHeat.map((party) => (
                <div key={party.party} className="grid grid-cols-[1.2fr_repeat(5,0.65fr)] gap-1 text-xs">
                  <div className="border border-white/20 bg-white/10 px-2 py-2 font-black uppercase text-white">
                    {shortLabel(party.party, 20)}
                    <span className="ml-2 font-mono text-[10px] text-white/45">{party.mpCount} MPs</span>
                  </div>
                  {[
                    party.corruptionIndex,
                    party.avgCriminalRisk,
                    party.avgAttendanceRisk,
                    party.avgParticipationRisk,
                    party.totalCases,
                  ].map((value, index) => (
                    <div
                      key={`${party.party}-${index}`}
                      className="flex items-center justify-center border border-white/20 px-1 py-2 font-mono font-black text-[#150f23]"
                      style={{ backgroundColor: index === 4 ? "#FB923C" : heatColor(Number(value)) }}
                      title={`${party.party}: ${value}`}
                    >
                      {value}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </AnalyticsCard>
        </div>

        <div className="mt-5 border-3 border-[#584674] bg-[#150f23]/90 p-4 shadow-[6px_6px_0_0_rgba(250,127,170,0.35)]">
          <div className="mb-4 flex flex-col justify-between gap-2 md:flex-row md:items-end">
            <div>
              <p className="font-mono text-[10px] font-black uppercase tracking-[0.2em] text-[#fa7faa]">Profiles to inspect first</p>
              <h3 className="text-xl font-black uppercase text-white">Most declared criminal cases</h3>
            </div>
            <p className="max-w-xl text-xs font-medium text-white/55">
              These are allegations/case declarations from source data, not findings of guilt. Click any row for the full profile and caveats.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            {data.criminalCaseLeaders.map((mp, index) => (
              <Link
                key={`${mp.mpName}-${mp.constituency}`}
                href={mp.href}
                className="group relative overflow-hidden border-3 border-white/80 bg-white p-3 text-[#150f23] shadow-[4px_4px_0_0_#79628c] transition hover:-translate-y-1 hover:shadow-[7px_7px_0_0_#c2ef4e]"
              >
                <div className="absolute right-2 top-2 border-2 border-[#150f23] bg-danger px-1.5 py-0.5 font-mono text-[10px] font-black text-white">
                  #{index + 1}
                </div>
                <div className="pr-10 text-sm font-black uppercase leading-tight group-hover:underline">{mp.mpName}</div>
                <div className="mt-1 text-xs font-bold text-slate-600">{mp.constituency}, {mp.state}</div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center font-mono">
                  <div className="border-2 border-[#150f23] bg-[#FEF9C3] p-1">
                    <div className="text-lg font-black">{mp.totalCases}</div>
                    <div className="text-[9px] font-black uppercase">Cases</div>
                  </div>
                  <div className="border-2 border-[#150f23] bg-red-100 p-1">
                    <div className="text-lg font-black text-danger">{mp.seriousCases}</div>
                    <div className="text-[9px] font-black uppercase">Serious</div>
                  </div>
                  <div className="border-2 border-[#150f23] bg-purple-100 p-1">
                    <div className="text-lg font-black">{mp.risk}</div>
                    <div className="text-[9px] font-black uppercase">{riskLabel(mp.risk)}</div>
                  </div>
                </div>
                <div className="mt-3 text-[10px] font-black uppercase tracking-wide text-danger">Open profile →</div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
