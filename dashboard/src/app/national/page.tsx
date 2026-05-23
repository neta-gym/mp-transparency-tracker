import Link from "next/link";
import { getAllEntries, getAllStates, getPartyStats } from "@/lib/data";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LeaderboardTable } from "@/components/LeaderboardTable";
import { formatScore } from "@/lib/format";
import { getScoreColor, getPartyColor, getPartyTextColor } from "@/lib/colors";

export const metadata = {
  title: "National Leaderboard — MP Transparency Tracker",
  description:
    "All-India MP transparency rankings across all scored states",
};

export default function NationalLeaderboardPage() {
  const allEntries = getAllEntries();
  const states = getAllStates();
  const partyStats = getPartyStats();

  const statesWithData = states.filter((s) => s.hasData);
  const totalMPs = allEntries.length;

  if (totalMPs === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
          >
            BACK
          </Link>
          <h1 className="text-3xl font-bold uppercase">National Leaderboard</h1>
        </div>
        <Card>
          <CardContent>
            <p className="text-text-muted py-8 text-center">
              No MP data available yet. Run the pipeline for at least one state first.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const avgScore =
    allEntries.reduce((sum, e) => sum + e.composite_score, 0) / totalMPs;
  const highestScore = Math.max(...allEntries.map((e) => e.composite_score));
  const lowestScore = Math.min(...allEntries.map((e) => e.composite_score));

  // Score distribution buckets
  const buckets = [
    { label: "80-100", range: [80, 101], color: "#047857" },
    { label: "60-79", range: [60, 80], color: "#059669" },
    { label: "40-59", range: [40, 60], color: "#FFAB00" },
    { label: "20-39", range: [20, 40], color: "#FF3D00" },
    { label: "0-19", range: [0, 20], color: "#FF1744" },
  ];

  const distribution = buckets.map((b) => ({
    ...b,
    count: allEntries.filter(
      (e) => e.composite_score >= b.range[0] && e.composite_score < b.range[1]
    ).length,
  }));

  const maxBucketCount = Math.max(...distribution.map((d) => d.count), 1);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
          >
            BACK
          </Link>
          <div>
            <h1 className="text-3xl font-bold uppercase tracking-tight text-ink">
              National Leaderboard
            </h1>
            <p className="text-text-secondary text-sm">
              {totalMPs} MPs across {statesWithData.length} states
            </p>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="text-center p-4 border-3 border-ink shadow-brutal bg-surface">
          <div className="text-3xl font-bold font-mono text-ink">{totalMPs}</div>
          <div className="text-xs text-text-muted uppercase tracking-wide mt-1">
            MPs Scored
          </div>
        </div>
        <div className="text-center p-4 border-3 border-ink shadow-brutal bg-surface">
          <div className="text-3xl font-bold font-mono text-ink">
            {statesWithData.length}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide mt-1">
            States
          </div>
        </div>
        <div className="text-center p-4 border-3 border-ink shadow-brutal bg-surface">
          <div
            className="text-3xl font-bold font-mono"
            style={{ color: getScoreColor(highestScore) }}
          >
            {formatScore(highestScore)}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide mt-1">
            Highest
          </div>
        </div>
        <div className="text-center p-4 border-3 border-ink shadow-brutal bg-surface">
          <div
            className="text-3xl font-bold font-mono"
            style={{ color: getScoreColor(avgScore) }}
          >
            {formatScore(avgScore)}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide mt-1">
            Average
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main table — 3 cols */}
        <div className="lg:col-span-3">
          <Card>
            <CardHeader>
              <CardTitle>All-India MP Rankings</CardTitle>
            </CardHeader>
            <CardContent>
              <LeaderboardTable
                entries={allEntries}
                showState={true}
                showPartyFilter={true}
                initialLimit={50}
              />
            </CardContent>
          </Card>
        </div>

        {/* Sidebar — 1 col */}
        <div className="space-y-6">
          {/* Score Distribution */}
          <Card>
            <CardHeader>
              <CardTitle>Score Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {distribution.map((d) => (
                  <div key={d.label} className="flex items-center gap-2">
                    <span className="text-xs font-mono w-10 text-right text-text-muted">
                      {d.label}
                    </span>
                    <div className="flex-1 h-5 bg-ink/5 border border-ink/20 relative">
                      <div
                        className="h-full transition-all"
                        style={{
                          width: `${(d.count / maxBucketCount) * 100}%`,
                          backgroundColor: d.color,
                          minWidth: d.count > 0 ? "4px" : "0",
                        }}
                      />
                    </div>
                    <span className="text-xs font-mono font-bold w-8 text-right">
                      {d.count}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Party Breakdown */}
          <Card>
            <CardHeader>
              <CardTitle>Party Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {partyStats.slice(0, 12).map((party) => {
                  const bgColor = getPartyColor(party.name);
                  const textColor = getPartyTextColor(party.name);
                  const partySlug = party.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
                  return (
                    <Link
                      key={party.name}
                      href={`/party/${partySlug}`}
                      className="flex items-center gap-2 p-2 border-b border-ink/10 hover:bg-highlight transition-colors group"
                    >
                      <span
                        className="text-[10px] font-bold px-1.5 py-0.5 border border-ink uppercase flex-shrink-0"
                        style={{ backgroundColor: bgColor, color: textColor }}
                      >
                        {party.name}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-text-muted">
                            {party.mpCount} MPs
                          </span>
                          <span
                            className="text-xs font-mono font-bold"
                            style={{ color: getScoreColor(party.avgScore) }}
                          >
                            {formatScore(party.avgScore)}
                          </span>
                        </div>
                        <div className="h-1 bg-ink/10 rounded-full mt-1">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${party.avgScore}%`,
                              backgroundColor: getScoreColor(party.avgScore),
                            }}
                          />
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* States with Data */}
          <Card>
            <CardHeader>
              <CardTitle>States Covered</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {statesWithData.map((state) => (
                  <Link
                    key={state.slug}
                    href={`/state/${state.slug}`}
                    className="flex items-center justify-between p-2 hover:bg-highlight transition-colors border-b border-ink/10 group"
                  >
                    <span className="text-sm font-bold text-ink group-hover:underline capitalize">
                      {state.displayName}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-muted">
                        {state.mpCount} MPs
                      </span>
                      {state.avgScore !== null && (
                        <span
                          className="text-xs font-mono font-bold"
                          style={{ color: getScoreColor(state.avgScore) }}
                        >
                          {formatScore(state.avgScore)}
                        </span>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
