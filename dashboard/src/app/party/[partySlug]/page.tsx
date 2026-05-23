import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllEntries, getPartyStats } from "@/lib/data";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LeaderboardTable } from "@/components/LeaderboardTable";
import { formatScore } from "@/lib/format";
import { getScoreColor, getPartyColor, getPartyTextColor } from "@/lib/colors";
import { SCORE_COMPONENTS } from "@/lib/types";

/** Generate static params for all parties */
export function generateStaticParams() {
  const partyStats = getPartyStats();
  return partyStats.map((p) => ({
    partySlug: p.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
  }));
}

/** Convert party slug back to party name for matching */
function partySlugToName(slug: string, partyStats: ReturnType<typeof getPartyStats>): string | null {
  for (const p of partyStats) {
    const pSlug = p.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    if (pSlug === slug) return p.name;
  }
  return null;
}

interface PageProps {
  params: Promise<{ partySlug: string }>;
}

export default async function PartyPage({ params }: PageProps) {
  const { partySlug } = await params;
  const partyStats = getPartyStats();
  const partyName = partySlugToName(partySlug, partyStats);

  if (!partyName) {
    notFound();
  }

  const partyStat = partyStats.find((p) => p.name === partyName)!;
  const allEntries = getAllEntries();
  const partyEntries = allEntries.filter((e) => e.party === partyName);

  if (partyEntries.length === 0) {
    notFound();
  }

  // Re-rank within party
  partyEntries.forEach((e, i) => (e.rank = i + 1));

  const bgColor = getPartyColor(partyName);
  const textColor = getPartyTextColor(partyName);

  // Compute per-dimension averages
  const dimensionAvgs = SCORE_COMPONENTS.map((sc) => {
    const avg =
      partyEntries.reduce((sum, e) => sum + (e[sc.key] as number), 0) /
      partyEntries.length;
    return {
      key: sc.key,
      label: sc.label,
      weight: sc.weight,
      avg: Math.round(avg * 10) / 10,
    };
  });

  // State breakdown
  const stateMap = new Map<string, { count: number; totalScore: number }>();
  for (const e of partyEntries) {
    const state = e.state;
    if (!stateMap.has(state)) stateMap.set(state, { count: 0, totalScore: 0 });
    const s = stateMap.get(state)!;
    s.count++;
    s.totalScore += e.composite_score;
  }
  const stateBreakdown = Array.from(stateMap.entries())
    .map(([state, data]) => ({
      state,
      count: data.count,
      avgScore: Math.round((data.totalScore / data.count) * 10) / 10,
    }))
    .sort((a, b) => b.count - a.count);

  // Strongest and weakest dimensions
  const sortedDims = [...dimensionAvgs].sort((a, b) => b.avg - a.avg);
  const strongest = sortedDims[0];
  const weakest = sortedDims[sortedDims.length - 1];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/national"
            className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
          >
            BACK
          </Link>
          <div className="flex items-center gap-3">
            <span
              className="text-lg font-bold px-3 py-1 border-3 border-ink uppercase"
              style={{ backgroundColor: bgColor, color: textColor }}
            >
              {partyName}
            </span>
            <div>
              <h1 className="text-2xl font-bold uppercase tracking-tight text-ink">
                Party Profile
              </h1>
              <p className="text-text-secondary text-sm">
                {partyStat.mpCount} MPs across {stateBreakdown.length} states
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="text-center p-4 border-3 border-ink shadow-brutal bg-surface">
          <div className="text-3xl font-bold font-mono text-ink">
            {partyStat.mpCount}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide mt-1">
            MPs
          </div>
        </div>
        <div className="text-center p-4 border-3 border-ink shadow-brutal bg-surface">
          <div
            className="text-3xl font-bold font-mono"
            style={{ color: getScoreColor(partyStat.avgScore) }}
          >
            {formatScore(partyStat.avgScore)}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide mt-1">
            Avg Score
          </div>
        </div>
        <div className="text-center p-4 border-3 border-ink shadow-brutal bg-surface">
          <div
            className="text-3xl font-bold font-mono"
            style={{ color: getScoreColor(strongest.avg) }}
          >
            {formatScore(strongest.avg)}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide mt-1">
            Best: {strongest.label}
          </div>
        </div>
        <div className="text-center p-4 border-3 border-ink shadow-brutal bg-surface">
          <div
            className="text-3xl font-bold font-mono"
            style={{ color: getScoreColor(weakest.avg) }}
          >
            {formatScore(weakest.avg)}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide mt-1">
            Weakest: {weakest.label}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main table — 3 cols */}
        <div className="lg:col-span-3">
          <Card>
            <CardHeader>
              <CardTitle>{partyName} MP Rankings</CardTitle>
            </CardHeader>
            <CardContent>
              <LeaderboardTable
                entries={partyEntries}
                showState={true}
                showPartyFilter={false}
                initialLimit={50}
              />
            </CardContent>
          </Card>
        </div>

        {/* Sidebar — 1 col */}
        <div className="space-y-6">
          {/* Dimension Averages */}
          <Card>
            <CardHeader>
              <CardTitle>Dimension Averages</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {dimensionAvgs.map((d) => (
                  <div key={d.key}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold uppercase text-text-muted">
                        {d.label}
                      </span>
                      <span
                        className="text-xs font-mono font-bold"
                        style={{ color: getScoreColor(d.avg) }}
                      >
                        {formatScore(d.avg)}
                      </span>
                    </div>
                    <div className="h-2 bg-ink/10 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${d.avg}%`,
                          backgroundColor: getScoreColor(d.avg),
                        }}
                      />
                    </div>
                    <div className="text-[10px] text-text-muted mt-0.5">
                      Weight: {Math.round(d.weight * 100)}%
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* State Breakdown */}
          <Card>
            <CardHeader>
              <CardTitle>By State</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {stateBreakdown.map((sb) => (
                  <Link
                    key={sb.state}
                    href={`/state/${sb.state.replace(/\s+/g, "-").toLowerCase()}`}
                    className="flex items-center justify-between p-2 hover:bg-highlight transition-colors border-b border-ink/10 group"
                  >
                    <span className="text-sm font-bold text-ink group-hover:underline capitalize">
                      {sb.state}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-muted">
                        {sb.count} MPs
                      </span>
                      <span
                        className="text-xs font-mono font-bold"
                        style={{ color: getScoreColor(sb.avgScore) }}
                      >
                        {formatScore(sb.avgScore)}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Other Parties */}
          <Card>
            <CardHeader>
              <CardTitle>Compare Parties</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {partyStats
                  .filter((p) => p.name !== partyName)
                  .slice(0, 8)
                  .map((p) => {
                    const pSlug = p.name
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/^-|-$/g, "");
                    const pBg = getPartyColor(p.name);
                    const pText = getPartyTextColor(p.name);
                    return (
                      <Link
                        key={p.name}
                        href={`/party/${pSlug}`}
                        className="flex items-center gap-2 p-2 hover:bg-highlight transition-colors border-b border-ink/10 group"
                      >
                        <span
                          className="text-[10px] font-bold px-1.5 py-0.5 border border-ink uppercase flex-shrink-0"
                          style={{ backgroundColor: pBg, color: pText }}
                        >
                          {p.name}
                        </span>
                        <div className="flex-1 flex items-center justify-between">
                          <span className="text-xs text-text-muted">
                            {p.mpCount} MPs
                          </span>
                          <span
                            className="text-xs font-mono font-bold"
                            style={{ color: getScoreColor(p.avgScore) }}
                          >
                            {formatScore(p.avgScore)}
                          </span>
                        </div>
                      </Link>
                    );
                  })}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
